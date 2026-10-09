"""GTK-free state and behaviour behind the OmniRename window."""

from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path
from typing import Callable

from care_cli import execute
from care_core import RenameError, RenameHistory

# Errors the JSON bridge raises for a refused or failed request.
BRIDGE_ERRORS = (RenameError, ValueError, TypeError, OSError)

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

READY_STATUS = "Press a pill to edit that part of the filename"

DEFAULT_COMMAND_KEY = "`"
# Key names that mean backtick even when the view cannot give its character, as with a dead key.
BACKTICK_KEYS = ("grave", "dead_grave")
ENTER_KEYS = ("Return", "KP_Enter")
MODIFIER_KEYS = ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R", "ISO_Level3_Shift")

CHEAT_SHEET = (
    "` + S     Cycle filename style\n"
    "` + 1     Add/edit Prefix       ` + 1x   Remove Prefix\n"
    "` + 2     Edit New Name          ` + 22   Suggest contextual name\n"
    "` + 22x   Remove suggestion      ` + 2c   Find and Replace\n"
    "` + 3     Add/edit Suffix       ` + 3x   Remove Suffix\n"
    "` + 4     Date YYYYMMDD          ` + 4c2  Date YYYYMM\n"
    "` + 4c3   Date YYYY             ` + 4x   Remove Date\n"
    "` + 5     Number defaults 112   ` + 5cXYZ Configure numbering\n"
    "` + 5x    Remove Number\n"
    "` + 41    Date then Prefix      ` + 14   Prefix then Date\n"
    "` + 53    Suffix then Number    ` + 35   Number then Suffix\n"
    "` + W     Save preset           ` + E    Cycle/load presets\n"
    "` + Esc   Revert; Esc again opens history\n"
    "` + ←/→   Move through visible fields\n"
    "Enter     Apply rename"
)


def default_settings_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "OmniRename" / "settings.json"


def load_command_key() -> str:
    """Return the configured Command Mode key, or backtick when the setting is missing or invalid.

    A valid key is one printable character that cannot appear in a Command code.
    """
    try:
        settings = json.loads(default_settings_path().read_text(encoding="utf-8"))
        key = settings["command_key"]
    except (OSError, ValueError, TypeError, KeyError):
        return DEFAULT_COMMAND_KEY
    if not isinstance(key, str) or len(key) != 1 or not key.isprintable() or key.isspace():
        return DEFAULT_COMMAND_KEY
    if (key.isascii() and key.isalnum()) or key == "?":
        return DEFAULT_COMMAND_KEY
    return key


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
        self.command_key = load_command_key()
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
        self.prefix_editing = False
        self.suffix_editing = False
        self.editor: str | None = None
        self.status = READY_STATUS
        self.rows: list[dict] = []
        self.safe = True
        self.editor_opened = 0
        self.command_mode = False
        self.command_key_held = False
        self.command_key_code: int | None = None
        self.command_key_name = ""
        self.status_before_command = ""
        self.typed_command = ""
        self.any_key_pressed = False
        self.held_keys: set[str | int] = set()
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
    def first_problem(self) -> str:
        """The first Problem in the Preview as "<original>: <problem>", or "" for a Safe Preview."""
        for row in self.rows:
            if row["problem"]:
                return row["original"] + ": " + row["problem"]
        return ""

    @property
    def item_count(self) -> str:
        return f"{len(self.paths)} item" + ("" if len(self.paths) == 1 else "s")

    @property
    def preview_list_visible(self) -> bool:
        """The Preview list shows for a batch, or for one item with a Problem."""
        return len(self.rows) > 1 or bool(self.first_problem)

    @property
    def visible_pills(self) -> list[str]:
        """The Pills of the Name Parts in use, in the order they appear in the name.

        Prefix and Suffix also show while empty right after their editor opens,
        until the next Command.
        """
        prefix = ["prefix"] if self.prefix or self.prefix_editing else []
        date = ["date"] if self.date_token else []
        suffix = ["suffix"] if self.suffix or self.suffix_editing else []
        number = ["number"] if self.options["counter_start"] is not None else []
        before = prefix + date if self.prefix_before_date else date + prefix
        after = number + suffix if self.options["counter_position"] == "before_suffix" else suffix + number
        return before + ["name"] + after

    def pill_step(self, current: str | None, step: int) -> str:
        """The visible Pill `step` places from `current`; a hidden or unknown `current` counts as the Name Pill."""
        pills = self.visible_pills
        index = pills.index(current if current in pills else "name")
        return pills[(index + step) % len(pills)]

    @property
    def cheat_sheet(self) -> str:
        return CHEAT_SHEET.replace("`", self.command_key)

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

    def key_down(self, key: str, char: str = "", code: int | None = None) -> bool:
        """Handle a key press; return True when the view should stop propagation.

        Command Mode lasts while the Command key is held. A press of a key that
        is already down is auto-repeat and is ignored. `code` identifies the
        physical key when the view knows it, so a key whose name changes with
        Shift still releases cleanly.
        """
        if self._is_command_key(key, char):
            if not self.command_key_held:
                self.end_command_mode()
                self.command_key_held = True
                self.command_key_code = code
                self.command_key_name = key
                self.command_mode = True
                self.status_before_command = self.status
                self.status = "⌁ Command mode — press the next key"
            return True
        if not self.command_mode and key in ENTER_KEYS:
            self.rename()
            return True
        if not self.command_mode:
            if key == "Escape" and self._clock() - self.last_escape < 1.2:
                self._requests.append(("open", "history"))
                self.last_escape = 0.0
                return True
            return False
        if key in MODIFIER_KEYS:
            return True
        if key in ("Left", "Right"):
            self.any_key_pressed = True
            self._requests.append(("focus_step", 1 if key == "Right" else -1))
            return True
        if self._key_identity(key, code) in self.held_keys:
            return True
        self.held_keys.add(self._key_identity(key, code))
        self.any_key_pressed = True
        if key == "Escape":
            self.end_command_mode()
            self._requests.append(("open", "confirm_revert"))
            return True
        if key in ENTER_KEYS:
            self.end_command_mode()
            self.rename()
            return True
        if char:
            self.typed_command += char.lower()
            self.status = "⌁ Command: " + self.command_key + " + " + self.typed_command
        return True

    def key_up(self, key: str, code: int | None = None) -> None:
        """Handle a key release; releasing the Command key runs the typed Command."""
        released_command_key = (bool(key) and key == self.command_key_name) or self._is_command_key(key, "")
        if not released_command_key and (code is None or code != self.command_key_code):
            self.held_keys.discard(self._key_identity(key, code))
            return
        self.command_key_held = False
        if not self.command_mode:
            return
        command = self.typed_command
        tapped = not self.any_key_pressed
        self.end_command_mode()
        if command:
            self.run_command(command)
            return
        self.status = self.status_before_command
        if tapped:
            self._requests.append(("insert_text", self.command_key))

    def focus_lost(self) -> None:
        """Cancel Command Mode without running anything; the release may never arrive."""
        if self.command_mode:
            self.status = self.status_before_command
        self.end_command_mode()
        self.command_key_held = False

    def end_command_mode(self) -> None:
        self.command_mode = False
        self.typed_command = ""
        self.any_key_pressed = False
        self.held_keys = set()

    def _is_command_key(self, key: str, char: str) -> bool:
        if self.command_key == DEFAULT_COMMAND_KEY and key in BACKTICK_KEYS:
            return True
        return char == self.command_key

    @staticmethod
    def _key_identity(key: str, code: int | None) -> str | int:
        return key if code is None else code

    def run_command(self, command: str) -> None:
        """Run one Command code."""
        self.status = "Command: " + self.command_key + " + " + command
        self.prefix_editing = False
        self.suffix_editing = False
        if command == "1":
            self.show_editor("prefix")
        elif command == "1x":
            self.prefix = ""
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
        else:
            self.status = "Unknown command: " + command

    # Commands

    def show_editor(self, key: str) -> None:
        self.editor = key
        self.editor_opened += 1
        self.status = EDITOR_HINTS.get(key, self.status)
        if key == "prefix":
            self.prefix_editing = True
            self._requests.append(("focus", "prefix"))
        elif key == "suffix":
            self.suffix_editing = True
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
        if self._bridge("save-preset", {"name": name, "preset": dict(self.options)}, "Preset not saved") is not None:
            self.status = "Preset saved: " + name.strip()
        return True

    def cycle_preset(self) -> None:
        listed = self._bridge("list-presets", {}, "Presets unavailable")
        if listed is None:
            return
        names = listed["names"]
        if not names:
            self.status = "No saved presets"
            return
        self.preset_index = (self.preset_index + 1) % len(names)
        result = self._bridge("load-preset", {"name": names[self.preset_index]}, "Preset not loaded")
        if result is None:
            return
        loaded = result["preset"]
        self.options.update(loaded)
        prefixes = list(loaded.get("prefixes", []))
        self.date_token = next((x for x in prefixes if str(x).isdigit() and len(str(x)) in (4, 6, 8)), "")
        self.prefix = next((x for x in prefixes if x != self.date_token), "")
        suffixes = list(loaded.get("suffixes", []))
        self.suffix = suffixes[0] if suffixes else ""
        self.prefix_editing = False
        self.suffix_editing = False
        loaded_name = str(self.options.get("name", ""))
        if loaded_name != self.name:
            self.suggested_names = None
        self.name = loaded_name
        self.status = "Preset: " + names[self.preset_index]
        self.preview()

    def history_entries(self) -> list[tuple[str, str]]:
        return list(RenameHistory().load().items())

    def restore_from_history(self, current_path: str) -> None:
        self._restore([current_path])

    def undo(self) -> None:
        self._restore(self.paths)

    def _restore(self, paths: list[str]) -> None:
        """Undo the recorded renames of `paths`, then preview the batch under its restored names."""
        try:
            originals = RenameHistory().load()
        except BRIDGE_ERRORS as error:
            self.status = "Undo failed: " + str(error)
            return
        result = self._bridge("undo", {"paths": paths}, "Undo failed")
        if result is None:
            return
        restored = result["paths"]
        if not restored:
            self.status = "Nothing to undo for these items"
            return
        self.paths = [originals.get(path, path) if path in paths else path for path in self.paths]
        self.preview()
        self.status = f"Restored {len(restored)} item" + ("" if len(restored) == 1 else "s")

    def suggest_names(self) -> None:
        result = self._bridge("recommend", {"paths": self.paths, "allow_agent": False, "include_content": False}, "No suggestion available")
        if result is None:
            return
        recommendations = result.get("recommendations", [])
        self.suggested_names = [item["suggested_name"] for item in recommendations] if recommendations else None
        self.status = "Contextual names suggested" if self.suggested_names else "No suggestion available"
        self.preview()

    def preview(self) -> None:
        """Recompute the Preview; a new Problem takes the status line until the next message."""
        previous_problem = self.first_problem
        self.options["name"] = self.name
        before = [self.prefix, self.date_token] if self.prefix_before_date else [self.date_token, self.prefix]
        self.options["prefixes"] = [value for value in before if value]
        self.options["suffixes"] = [self.suffix] if self.suffix else []
        command = "preview-manual" if self.suggested_names else "preview"
        result = self._bridge(command, self._rename_payload(), "Preview failed")
        if result is None:
            self.rows = []
            self.safe = False
            return
        self.rows = [{**item, "problem": "" if item["safe"] else item["status"]} for item in result.get("items", [])]
        self.safe = bool(result.get("safe", True))
        problem = self.first_problem
        if problem and problem != previous_problem:
            self.status = problem
        elif not problem and previous_problem and self.status == previous_problem:
            self.status = READY_STATUS

    def _bridge(self, command: str, payload: dict, failure: str) -> dict | None:
        """Run one bridge command; on failure show "<failure>: <reason>" and return None."""
        try:
            return execute(command, payload)
        except BRIDGE_ERRORS as error:
            self.status = failure + ": " + str(error)
            return None

    def _rename_payload(self) -> dict:
        return {"paths": self.paths, "options": self.options, "names": self.suggested_names or []}

    def rename(self) -> None:
        """Rename only a Safe Preview, with the Suggestions when they are active."""
        self.preview()
        if not self.safe:
            self.status = self.first_problem or self.status
            return
        command = "apply-manual" if self.suggested_names else "apply"
        if self._bridge(command, self._rename_payload(), "Rename failed") is None:
            return
        self._requests.append(("close",))

    def revert(self) -> None:
        self.name = ""
        self.prefix = ""
        self.suffix = ""
        self.prefix_editing = False
        self.suffix_editing = False
        self.options.update({"name": "", "prefixes": [], "suffixes": [], "counter_start": None, "find": "", "replace": ""})
        self.date_token = ""
        self.suggested_names = None
        self.preview()
        self.status = "Original name restored"
