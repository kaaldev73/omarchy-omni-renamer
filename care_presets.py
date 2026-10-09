"""Persistent, user-scoped naming presets for OmniRename."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def default_presets_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "OmniRename" / "presets.json"


class PresetStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_presets_path()

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            presets = data.get("presets", {})
            if not isinstance(presets, dict) or not all(
                isinstance(name, str) and isinstance(value, dict)
                for name, value in presets.items()
            ):
                raise ValueError
            return presets
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise ValueError("The preset file is unreadable.") from error

    @staticmethod
    def _validate_name(name: str) -> str:
        cleaned = name.strip()
        if not cleaned or len(cleaned) > 50 or any(ord(char) < 32 for char in cleaned):
            raise ValueError("Preset name must be 1–50 visible characters.")
        return cleaned

    def names(self) -> list[str]:
        return sorted(self._read(), key=str.casefold)

    def load(self, name: str) -> dict:
        cleaned = self._validate_name(name)
        presets = self._read()
        if cleaned not in presets:
            raise ValueError(f'Preset "{cleaned}" was not found.')
        return presets[cleaned]

    def save(self, name: str, preset: dict) -> None:
        cleaned = self._validate_name(name)
        if not isinstance(preset, dict):
            raise ValueError("Preset settings must be an object.")
        presets = self._read()
        presets[cleaned] = preset
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "presets": presets}, ensure_ascii=False, indent=2)
        temporary_name = ""
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as temporary:
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_name = temporary.name
            os.replace(temporary_name, self.path)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)
