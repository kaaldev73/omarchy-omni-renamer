"""Safe, platform-independent filename transformation and rename transactions."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Iterable


CASE_STYLES = (
    "kebab-case",
    "PascalCase",
    "snake_case",
    "camelCase",
    "UPPERCASE",
    "lowercase",
    "Title Case",
    "Sentence case",
)

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_COMPOUND_EXTENSIONS = (".tar.gz", ".tar.bz2", ".tar.xz")


class RenameError(RuntimeError):
    """Raised when a rename plan cannot be safely completed."""


@dataclass(frozen=True)
class NamingOptions:
    case_style: str = "kebab-case"
    name: str = ""
    prefixes: tuple[str, ...] = ()
    suffixes: tuple[str, ...] = ()
    find: str = ""
    replace: str = ""
    use_regex: bool = False
    case_sensitive: bool = False
    counter_start: int | None = None
    counter_step: int = 1
    counter_padding: int = 2
    counter_position: str = "suffix"
    trim_start: int = 0
    trim_end: int = 0
    person: str = ""
    person_position: str = "suffix"


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


def _split_extension(filename: str) -> tuple[str, str]:
    lowered = filename.lower()
    for extension in _COMPOUND_EXTENSIONS:
        if lowered.endswith(extension):
            return filename[: -len(extension)], filename[-len(extension) :]
    return os.path.splitext(filename)


def _words(value: str) -> list[str]:
    value = value.replace("_", " ")
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    value = re.sub(r"([A-Za-z])([0-9])|([0-9])([A-Za-z])", r"\1\3 \2\4", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return [word for word in value.strip().split() if word]


def _convert_stem(stem: str, style: str) -> str:
    if style not in CASE_STYLES:
        raise ValueError(f"Unsupported case style: {style}")
    words = _words(stem)
    if not words:
        return ""
    if style == "kebab-case":
        return "-".join(word.lower() for word in words)
    if style == "snake_case":
        return "_".join(word.lower() for word in words)
    if style == "PascalCase":
        return "".join(word[:1].upper() + word[1:].lower() for word in words)
    if style == "camelCase":
        return words[0].lower() + "".join(
            word[:1].upper() + word[1:].lower() for word in words[1:]
        )
    if style == "UPPERCASE":
        return " ".join(words).upper()
    if style == "lowercase":
        return " ".join(words).lower()
    if style == "Title Case":
        return " ".join(word.capitalize() for word in words)
    return " ".join(words).lower().capitalize()


def date_prefixes(value: date, formats: Iterable[str]) -> tuple[str, ...]:
    supported = {"yyyymmdd": "%Y%m%d", "yyyymm": "%Y%m", "yyyy": "%Y"}
    return tuple(value.strftime(supported[item]) for item in formats if item in supported)


def transform_filename(
    filename: str,
    options: NamingOptions,
    *,
    preserve_extension: bool = True,
    index: int = 0,
) -> str:
    stem, extension = _split_extension(filename) if preserve_extension else (filename, "")
    if options.trim_start:
        stem = stem[max(0, options.trim_start) :]
    if options.trim_end:
        stem = stem[: -max(0, options.trim_end)] if options.trim_end < len(stem) else ""
    if options.find:
        flags = 0 if options.case_sensitive else re.IGNORECASE
        pattern = options.find if options.use_regex else re.escape(options.find)
        try:
            stem = re.sub(pattern, options.replace, stem, flags=flags)
        except re.error as error:
            raise ValueError(f"Invalid regular expression: {error}") from error
    converted = _convert_stem(options.name.strip() if options.name.strip() else stem, options.case_style)
    separator = "_" if options.case_style == "snake_case" else "-"
    prefixes = list(options.prefixes)
    suffixes = list(options.suffixes)
    if options.person.strip():
        if options.person_position == "prefix":
            prefixes.append(options.person)
        else:
            suffixes.insert(0, options.person)
    if options.counter_start is not None:
        counter = options.counter_start + index * options.counter_step
        token = str(counter).zfill(max(1, options.counter_padding))
        if options.counter_position == "prefix":
            prefixes.append(token)
        elif options.counter_position == "before_suffix":
            suffixes.insert(0, token)
        else:
            suffixes.append(token)
    decorations = (*prefixes, converted, *suffixes)
    clean = [part.strip(" .-_") for part in decorations if part.strip(" .-_")]
    result = separator.join(clean) + extension
    if not clean:
        raise ValueError("The selected options produce an empty filename.")
    if any(character in result for character in '<>:"/\\|?*'):
        raise ValueError("The filename contains a character Windows does not allow.")
    if any(ord(character) < 32 for character in result):
        raise ValueError("The filename contains a control character Windows does not allow.")
    if result.rstrip(" .") != result:
        raise ValueError("Windows filenames cannot end with a space or period.")
    if clean[0].split(".")[0].upper() in _WINDOWS_RESERVED:
        raise ValueError("The filename is reserved by Windows.")
    if len(result) > 255:
        raise ValueError("The filename exceeds the 255-character limit.")
    return result


def build_rename_plan(paths: Iterable[Path | str], options: NamingOptions) -> RenamePlan:
    source_paths = tuple(Path(path) for path in paths)
    source_keys = {str(path.absolute()).casefold() for path in source_paths}
    provisional: list[RenameItem] = []
    destination_counts: dict[str, int] = {}

    for index, source in enumerate(source_paths):
        try:
            destination = source.with_name(
                transform_filename(
                    source.name,
                    options,
                    preserve_extension=not source.is_dir(),
                    index=index,
                )
            )
            problem = "" if source.exists() else "Source no longer exists"
        except ValueError as error:
            destination = source
            problem = str(error)
        key = str(destination.absolute()).casefold()
        destination_counts[key] = destination_counts.get(key, 0) + 1
        provisional.append(RenameItem(source, destination, problem))

    result: list[RenameItem] = []
    for item in provisional:
        problem = item.problem
        destination_key = str(item.destination.absolute()).casefold()
        if not problem and destination_counts[destination_key] > 1:
            problem = "More than one item would receive this name"
        elif (
            not problem
            and item.changed
            and item.destination.exists()
            and destination_key not in source_keys
        ):
            problem = "A file or folder with this name already exists"
        result.append(replace(item, problem=problem))
    return RenamePlan(tuple(result))


def build_manual_plan(renames: Iterable[tuple[Path | str, str]]) -> RenamePlan:
    """Validate user- or agent-proposed basenames without transforming them."""
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
        self._execute_pairs(pairs)
        history = self.history.load()
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
