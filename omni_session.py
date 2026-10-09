"""GTK-free state and behaviour behind the OmniRename window."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Callable

from care_cli import execute
from care_core import RenameHistory

# Order of the `s` Command cycle; Title Case is deliberately not in the cycle.
STYLES = ["kebab-case", "snake_case", "PascalCase", "camelCase", "UPPERCASE", "lowercase", "Sentence case"]

EDITOR_HINTS = {
    "date": "Choose YYYYMMDD, YYYYMM, or YYYY",
    "prefix": "Prefix text appears before the name",
    "suffix": "Suffix text appears after the name",
    "number": "Choose sequence start, step, and digits",
    "replace": "Find text and replace it in the filename",
    "style": "Choose how words are separated and capitalized",
}

COMMAND_KEYS = ("grave", "dead_grave")
ENTER_KEYS = ("Return", "KP_Enter")
COMMAND_DELAY_MS = 1500


class RenameSession:
    """Holds the rules for one batch and turns key and field input into a Preview.

    The view forwards input, redraws from the readable state, and handles the
    requests returned by take_requests().
    """

    def __init__(
        self,
        paths: list[str],
        *,
        today: Callable[[], date] = date.today,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.paths = paths
        self._today = today
        self._clock = clock
        self.options = {
            "case_style": "kebab-case",
            "name": "",
            "prefixes": [],
            "suffixes": [],
            "counter_start": None,
            "counter_step": 1,
            "counter_padding": 2,
            "counter_position": "suffix",
        }
        self.name = ""
        self.prefix = ""
        self.suffix = ""
        self.date_token = ""
        self.prefix_before_date = False
        self.suggested_names: list[str] | None = None
        self.prefix_shown = False
        self.suffix_shown = False
        self.editor: str | None = None
        self.status = "Press a pill to edit that part of the filename"
        self.rows: list[dict] = []
        self.safe = True
        self.editor_opened = 0
        self.command_mode = False
        self.typed_command = ""
        self.last_escape = 0.0
        self.preset_index = -1
        self._requests: list[tuple] = []
        self.preview()

    # Readable state

    @property
    def original_name(self) -> str:
        return self.paths[0].rsplit("/", 1)[-1] if self.paths else "OldName.type"

    @property
    def new_name(self) -> str:
        return self.rows[0]["renamed"] if self.rows else "NewName.type"

    @property
    def visible_pills(self) -> list[str]:
        pills = []
        if self.prefix_shown:
            pills.append("prefix")
        pills.append("name")
        if self.suffix_shown:
            pills.append("suffix")
        return pills

    @property
    def command_pending(self) -> bool:
        return self.command_mode and bool(self.typed_command)

    def take_requests(self) -> list[tuple]:
        requests, self._requests = self._requests, []
        return requests

    # Field input

    def set_name(self, value: str) -> None:
        self.name = value
        self.suggested_names = None
        self.preview()

    def set_prefix(self, value: str) -> None:
        self.prefix = value
        self.preview()

    def set_suffix(self, value: str) -> None:
        self.suffix = value
        self.preview()

    def set_find(self, value: str) -> None:
        self.options["find"] = value
        self.preview()

    def set_replace(self, value: str) -> None:
        self.options["replace"] = value
        self.preview()

    def set_date(self, fmt: str, enabled: bool) -> None:
        self.date_token = self._today().strftime(fmt) if enabled else ""
        self.preview()

    def set_number(self, enabled: bool) -> None:
        self.options["counter_start"] = 1 if enabled else None
        self.preview()

    # Key input

    def key_down(self, key: str, char: str = "") -> bool:
        """Handle a key press; return True when the view should stop propagation."""
        if not self.command_mode and key in ENTER_KEYS:
            self.rename()
            return True
        if not self.command_mode and (char == "`" or key in COMMAND_KEYS):
            self.command_mode = True
            self.typed_command = ""
            self.status = "⌁ Command mode — press the next key"
            return True
        if not self.command_mode:
            if key == "Escape" and self._clock() - self.last_escape < 1.2:
                self._requests.append(("open", "history"))
                self.last_escape = 0.0
                return True
            return False
        if key in ("Left", "Right"):
            self._requests.append(("focus_step", 1 if key == "Right" else -1))
            return True
        if key == "Escape":
            self.command_mode = False
            self.typed_command = ""
            self._requests.append(("open", "confirm_revert"))
            return True
        if key in ENTER_KEYS:
            self.command_mode = False
            self.rename()
            return True
        if char:
            self.typed_command += char.lower()
            self.status = "⌁ Command: ` + " + self.typed_command
        return True

    def key_up(self, key: str) -> None:
        """Handle a key release; Commands do not use releases yet."""

    def focus_lost(self) -> None:
        """Handle the window losing focus; Commands do not use it yet."""

    def run_command(self) -> None:
        """Run the typed Command; the view calls this once typing pauses."""
        command = self.typed_command
        self.typed_command = ""
        self.command_mode = False
        self.status = "Command: ` + " + command
        if command == "1":
            self.show_editor("prefix")
        elif command == "1x":
            self.prefix = ""
            self.prefix_shown = False
            self.options["prefixes"] = []
            self.preview()
        elif command in ("31", "14"):
            self.prefix_before_date = True
            self.preview()
        elif command in ("13", "41"):
            self.prefix_before_date = False
            self.preview()
        elif command == "2":
            self._requests.append(("focus", "name"))
        elif command == "s":
            self.cycle_style()
        elif command == "3":
            self.show_editor("suffix")
        elif command == "3x":
            self.suffix = ""
            self.suffix_shown = False
            self.options["suffixes"] = []
            self.preview()
        elif command == "53":
            self.options["counter_position"] = "suffix"
            self.preview()
        elif command == "35":
            self.options["counter_position"] = "before_suffix"
            self.preview()
        elif command == "4":
            self.apply_date("%Y%m%d", "YYYYMMDD")
        elif command == "4c2":
            self.apply_date("%Y%m", "YYYYMM")
        elif command == "4c3":
            self.apply_date("%Y", "YYYY")
        elif command == "4x":
            self.date_token = ""
            self.status = "Date removed"
            self.preview()
        elif command == "22":
            self.suggest_names()
        elif command == "22x":
            self.suggested_names = None
            self.status = "AI suggestion removed"
            self.preview()
        elif command == "2c":
            self.show_editor("replace")
        elif command == "5":
            self.configure_number(1, 1, 2)
        elif command.startswith("5c") and len(command) == 5 and command[2:].isdigit():
            self.configure_number(int(command[2]), int(command[3]), int(command[4]))
        elif command == "5x":
            self.set_number(False)
            self.status = "Numbering removed"
        elif command == "u":
            self.undo()
        elif command == "w":
            self._requests.append(("open", "save_preset"))
        elif command == "e":
            self.cycle_preset()
        elif command == "?":
            self._requests.append(("open", "shortcuts"))
        elif command == "return":
            self.rename()

    # Commands

    def show_editor(self, key: str) -> None:
        self.editor = key
        self.editor_opened += 1
        self.status = EDITOR_HINTS.get(key, self.status)
        if key == "prefix":
            self.prefix_shown = True
            self._requests.append(("focus", "prefix"))
        elif key == "suffix":
            self.suffix_shown = True
            self._requests.append(("focus", "suffix"))
        elif key == "replace":
            self._requests.append(("focus", "find"))
        elif key == "name":
            self._requests.append(("focus", "name"))

    def cycle_style(self) -> None:
        current = STYLES.index(self.options["case_style"])
        self.options["case_style"] = STYLES[(current + 1) % len(STYLES)]
        self.suggested_names = None
        self.preview()
        self.status = "Style: " + self.options["case_style"]

    def apply_date(self, fmt: str, label: str) -> None:
        self.date_token = self._today().strftime(fmt)
        self.status = "Date enabled: " + label
        self.preview()

    def configure_number(self, start: int, step: int, digits: int) -> None:
        self.options["counter_start"] = start
        self.options["counter_step"] = step
        self.options["counter_padding"] = max(1, digits)
        self.status = f"Numbering: start {start}, step {step}, digits {digits}"
        self.preview()

    def save_preset(self, name: str) -> bool:
        if not name.strip():
            return False
        execute("save-preset", {"name": name, "preset": dict(self.options)})
        self.status = "Preset saved: " + name.strip()
        return True

    def cycle_preset(self) -> None:
        names = execute("list-presets", {})["names"]
        if not names:
            self.status = "No saved presets"
            return
        self.preset_index = (self.preset_index + 1) % len(names)
        loaded = execute("load-preset", {"name": names[self.preset_index]})["preset"]
        self.options.update(loaded)
        prefixes = list(loaded.get("prefixes", []))
        self.date_token = next((x for x in prefixes if str(x).isdigit() and len(str(x)) in (4, 6, 8)), "")
        self.prefix = next((x for x in prefixes if x != self.date_token), "")
        suffixes = list(loaded.get("suffixes", []))
        self.suffix = suffixes[0] if suffixes else ""
        self.prefix_shown = bool(self.prefix)
        self.suffix_shown = bool(self.suffix)
        loaded_name = str(self.options.get("name", ""))
        if loaded_name != self.name:
            self.suggested_names = None
        self.name = loaded_name
        self.status = "Preset: " + names[self.preset_index]
        self.preview()

    def history_entries(self) -> list[tuple[str, str]]:
        return list(RenameHistory().load().items())

    def restore_from_history(self, current_path: str) -> None:
        execute("undo", {"paths": [current_path]})
        self.preview()

    def suggest_names(self) -> None:
        result = execute("recommend", {"paths": self.paths, "allow_agent": False, "include_content": False})
        recommendations = result.get("recommendations", [])
        self.suggested_names = [item["suggested_name"] for item in recommendations] if recommendations else None
        self.status = "Contextual names suggested" if self.suggested_names else "No suggestion available"
        self.preview()

    def preview(self) -> None:
        self.options["name"] = self.name
        before = [self.prefix, self.date_token] if self.prefix_before_date else [self.date_token, self.prefix]
        self.options["prefixes"] = [value for value in before if value]
        self.options["suffixes"] = [self.suffix] if self.suffix else []
        command = "preview-manual" if self.suggested_names else "preview"
        payload = {"paths": self.paths, "options": self.options, "names": self.suggested_names or []}
        result = execute(command, payload)
        self.rows = result.get("items", [])
        self.safe = bool(result.get("safe", True))

    def rename(self) -> None:
        if execute("apply", {"paths": self.paths, "options": self.options}).get("ok"):
            self._requests.append(("close",))

    def undo(self) -> None:
        execute("undo", {"paths": self.paths})
        self.preview()

    def revert(self) -> None:
        self.name = ""
        self.prefix = ""
        self.suffix = ""
        self.prefix_shown = False
        self.suffix_shown = False
        self.options.update({"name": "", "prefixes": [], "suffixes": [], "counter_start": None, "find": "", "replace": ""})
        self.date_token = ""
        self.suggested_names = None
        self.preview()
        self.status = "Original name restored"
