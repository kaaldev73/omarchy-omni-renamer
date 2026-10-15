"""Safe, all-or-nothing renames with undo history."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable


class RenameError(RuntimeError):
    """Raised when a rename plan cannot be safely completed."""


@dataclass(frozen=True)
class RenameItem:
    source: Path
    destination: Path
    problem: str = ""

    @property
    def changed(self) -> bool:
        return self.source != self.destination


@dataclass(frozen=True)
class RenamePlan:
    items: tuple[RenameItem, ...]

    @property
    def is_safe(self) -> bool:
        return all(not item.problem for item in self.items)

    @property
    def changed_items(self) -> tuple[RenameItem, ...]:
        return tuple(item for item in self.items if item.changed)


def default_history_path() -> Path:
    """Return a writable, persistent per-user history location."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "OmniRename" / "rename-history.json"


def build_manual_plan(renames: Iterable[tuple[Path | str, str]]) -> RenamePlan:
    """Validate proposed basenames, recording a Problem per item that cannot be renamed."""
    pairs = [(Path(source), str(name)) for source, name in renames]
    source_keys = {str(source.absolute()).casefold() for source, _ in pairs}
    counts: dict[str, int] = {}
    provisional: list[RenameItem] = []
    for source, name in pairs:
        problem = ""
        if Path(name).name != name or name in ("", ".", ".."):
            problem = "The proposed name must be a single filename"
            destination = source
        else:
            destination = source.with_name(name)
            if any(character in name for character in "/\0") or any(
                ord(character) < 32 for character in name
            ):
                problem = "The proposed name contains an invalid character"
            elif len(name) > 255:
                problem = "The proposed name exceeds the 255-character limit"
            elif not source.exists():
                problem = "Source no longer exists"
        key = str(destination.absolute()).casefold()
        counts[key] = counts.get(key, 0) + 1
        provisional.append(RenameItem(source, destination, problem))
    items = []
    for item in provisional:
        problem = item.problem
        key = str(item.destination.absolute()).casefold()
        if not problem and counts[key] > 1:
            problem = "More than one item would receive this name"
        elif not problem and item.changed and item.destination.exists() and key not in source_keys:
            problem = "A file or folder with this name already exists"
        items.append(replace(item, problem=problem))
    return RenamePlan(tuple(items))


class RenameHistory:
    def __init__(self, path: Path | None = None):
        self.path = path or default_history_path()

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            renames = data["renames"]
            if not isinstance(renames, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in renames.items()
            ):
                raise ValueError("invalid rename mapping")
            return dict(renames)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise RenameError(
                f"Undo history is unreadable. Preserve this file for recovery: {self.path}"
            ) from error

    def save(self, renames: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "renames": renames}, indent=2)
        handle, temporary_name = tempfile.mkstemp(
            prefix="rename-history-", suffix=".json", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as temporary:
                temporary.write(payload)
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


class RenameTransaction:
    def __init__(self, history: RenameHistory | None = None):
        self.history = history or RenameHistory()

    def apply(self, plan: RenamePlan) -> list[Path]:
        if not plan.is_safe:
            raise RenameError("Resolve the preview errors before renaming.")
        pairs = [(item.source, item.destination) for item in plan.changed_items]
        history = self.history.load()
        self._execute_pairs(pairs)
        for source, destination in pairs:
            history[str(destination)] = str(source)
        try:
            self.history.save(history)
        except Exception as error:
            self._execute_pairs([(destination, source) for source, destination in pairs])
            raise RenameError(f"Could not save undo history: {error}") from error
        return [destination for _, destination in pairs]

    def undo(self, selected_paths: Iterable[Path | str]) -> list[Path]:
        history = self.history.load()
        pairs: list[tuple[Path, Path]] = []
        for selected in map(Path, selected_paths):
            original = history.get(str(selected))
            if original:
                destination = Path(original)
                if destination.exists():
                    raise RenameError(f"Cannot restore {selected.name}: {destination.name} exists.")
                pairs.append((selected, destination))
        if not pairs:
            return []
        self._execute_pairs(pairs)
        for selected, _ in pairs:
            history.pop(str(selected), None)
        try:
            self.history.save(history)
        except Exception as error:
            self._execute_pairs([(destination, selected) for selected, destination in pairs])
            raise RenameError(f"Could not update undo history: {error}") from error
        return [destination for _, destination in pairs]

    @staticmethod
    def _execute_pairs(pairs: list[tuple[Path, Path]]) -> None:
        sources = {str(source.absolute()).casefold() for source, _ in pairs}
        destinations: set[str] = set()
        for source, destination in pairs:
            if not source.exists():
                raise RenameError(f"Source no longer exists: {source}")
            destination_key = str(destination.absolute()).casefold()
            if destination_key in destinations:
                raise RenameError(f"More than one item would become: {destination.name}")
            destinations.add(destination_key)
            if destination.exists() and destination_key not in sources:
                raise RenameError(f"Destination now exists: {destination}")

        staged: list[tuple[Path, Path, Path]] = []
        completed: list[tuple[Path, Path, Path]] = []
        try:
            for source, destination in pairs:
                temporary = source.with_name(f".care-{uuid.uuid4().hex}.tmp")
                source.rename(temporary)
                staged.append((source, temporary, destination))
            for source, temporary, destination in staged:
                if destination.exists():
                    raise FileExistsError(f"Destination now exists: {destination}")
                temporary.rename(destination)
                completed.append((source, temporary, destination))
        except Exception as error:
            rollback_failures: list[str] = []
            for source, temporary, destination in reversed(staged):
                current = destination if (source, temporary, destination) in completed else temporary
                if current.exists() and not source.exists():
                    try:
                        current.rename(source)
                    except OSError as rollback_error:
                        rollback_failures.append(f"{current} → {source}: {rollback_error}")
            if rollback_failures:
                details = "; ".join(rollback_failures)
                raise RenameError(
                    f"Rename failed and rollback is incomplete: {error}. Recovery details: {details}"
                ) from error
            raise RenameError(f"Rename failed; all staged changes were rolled back: {error}") from error
