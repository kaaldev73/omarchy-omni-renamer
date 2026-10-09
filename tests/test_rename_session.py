import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from care_cli import execute
from care_core import RenameError
from omni_session import RenameSession


class SessionTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        environment = mock.patch.dict(
            os.environ,
            {"XDG_STATE_HOME": str(self.root / "state"), "XDG_CONFIG_HOME": str(self.root / "config")},
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.files = self.root / "files"
        self.files.mkdir()

    def session_for(self, *names):
        paths = []
        for name in names:
            path = self.files / name
            path.write_text("x", encoding="utf-8")
            paths.append(str(path))
        return RenameSession(paths, today=lambda: date(2024, 3, 9))

    def command(self, session, code):
        session.key_down("grave", "`")
        for char in code:
            session.key_down(char, char)
            session.key_up(char)
        session.key_up("grave")


class StyleCommandTests(SessionTestCase):
    def test_style_command_cycles_to_the_next_style(self):
        session = self.session_for("Quarterly Report.txt")
        self.assertEqual(session.new_name, "quarterly-report.txt")
        self.command(session, "s")
        self.assertEqual(session.new_name, "quarterly_report.txt")
        self.assertEqual(session.status, "Style: snake_case")

    def test_uppercase_style_command_works_like_lowercase(self):
        session = self.session_for("Quarterly Report.txt")
        self.command(session, "S")
        self.assertEqual(session.new_name, "quarterly_report.txt")

    def test_style_cycles_back_to_the_first_style(self):
        session = self.session_for("Quarterly Report.txt")
        for _ in range(7):
            self.command(session, "s")
        self.assertEqual(session.new_name, "quarterly-report.txt")


class NamePartCommandTests(SessionTestCase):
    def test_prefix_command_shows_the_prefix_pill_and_focuses_it(self):
        session = self.session_for("notes.txt")
        self.assertEqual(session.visible_pills, ["name"])
        self.command(session, "1")
        self.assertEqual(session.visible_pills, ["prefix", "name"])
        self.assertEqual(session.take_requests(), [("focus", "prefix")])
        session.set_prefix("client")
        self.assertEqual(session.new_name, "client-notes.txt")

    def test_remove_prefix_command_clears_and_hides_it(self):
        session = self.session_for("notes.txt")
        self.command(session, "1")
        session.set_prefix("client")
        self.command(session, "1x")
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.visible_pills, ["name"])
        self.assertEqual(session.prefix, "")

    def test_suffix_command_and_its_removal(self):
        session = self.session_for("notes.txt")
        self.command(session, "3")
        self.assertEqual(session.visible_pills, ["name", "suffix"])
        session.set_suffix("final")
        self.assertEqual(session.new_name, "notes-final.txt")
        self.command(session, "3x")
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.visible_pills, ["name"])

    def test_name_command_focuses_the_name(self):
        session = self.session_for("notes.txt")
        self.command(session, "2")
        self.assertEqual(session.take_requests(), [("focus", "name")])
        session.set_name("Meeting Minutes")
        self.assertEqual(session.new_name, "meeting-minutes.txt")

    def test_date_commands_add_each_format_and_remove_it(self):
        session = self.session_for("notes.txt")
        self.command(session, "4")
        self.assertEqual(session.new_name, "20240309-notes.txt")
        self.command(session, "4c2")
        self.assertEqual(session.new_name, "202403-notes.txt")
        self.command(session, "4c3")
        self.assertEqual(session.new_name, "2024-notes.txt")
        self.assertEqual(session.status, "Date enabled: YYYY")
        self.command(session, "4x")
        self.assertEqual(session.new_name, "notes.txt")

    def test_prefix_and_date_order_commands(self):
        session = self.session_for("notes.txt")
        session.set_prefix("client")
        self.command(session, "4")
        self.assertEqual(session.new_name, "20240309-client-notes.txt")
        for code, expected in (
            ("14", "client-20240309-notes.txt"),
            ("41", "20240309-client-notes.txt"),
            ("31", "client-20240309-notes.txt"),
            ("13", "20240309-client-notes.txt"),
        ):
            self.command(session, code)
            self.assertEqual(session.new_name, expected, code)

    def test_number_commands(self):
        session = self.session_for("notes.txt")
        self.command(session, "5")
        self.assertEqual(session.new_name, "notes-01.txt")
        self.command(session, "5c734")
        self.assertEqual(session.new_name, "notes-0007.txt")
        self.assertEqual(session.status, "Numbering: start 7, step 3, digits 4")
        self.command(session, "5x")
        self.assertEqual(session.new_name, "notes.txt")

    def test_number_steps_across_a_batch(self):
        session = self.session_for("a.txt", "b.txt")
        self.command(session, "5c132")
        self.assertEqual([row["renamed"] for row in session.rows], ["a-01.txt", "b-04.txt"])

    def test_number_and_suffix_order_commands(self):
        session = self.session_for("notes.txt")
        session.set_suffix("final")
        self.command(session, "5")
        self.assertEqual(session.new_name, "notes-final-01.txt")
        self.command(session, "35")
        self.assertEqual(session.new_name, "notes-01-final.txt")
        self.command(session, "53")
        self.assertEqual(session.new_name, "notes-final-01.txt")

    def test_find_and_replace_command_opens_the_replace_editor(self):
        session = self.session_for("draft notes.txt")
        self.command(session, "2c")
        self.assertEqual(session.editor, "replace")
        self.assertEqual(session.take_requests(), [("focus", "find")])
        session.set_find("draft")
        session.set_replace("final")
        self.assertEqual(session.new_name, "final-notes.txt")


class SuggestionCommandTests(SessionTestCase):
    def test_suggestion_replaces_the_preview_and_can_be_removed(self):
        session = self.session_for("IMG 0001.txt")
        self.command(session, "s")
        self.assertEqual(session.new_name, "img_0001.txt")
        self.command(session, "22")
        self.assertEqual(session.status, "Contextual names suggested")
        self.assertEqual(session.new_name, "img-0001.txt")
        self.command(session, "22x")
        self.assertEqual(session.status, "AI suggestion removed")
        self.assertEqual(session.new_name, "img_0001.txt")


class PresetCommandTests(SessionTestCase):
    def test_saved_preset_is_restored_by_the_cycle_command(self):
        session = self.session_for("notes.txt")
        session.set_prefix("client")
        self.command(session, "s")
        self.command(session, "w")
        self.assertEqual(session.take_requests(), [("open", "save_preset")])
        self.assertTrue(session.save_preset("Client snake"))
        self.assertEqual(session.status, "Preset saved: Client snake")

        fresh = self.session_for("other notes.txt")
        self.command(fresh, "e")
        self.assertEqual(fresh.new_name, "client_other_notes.txt")
        self.assertEqual(fresh.visible_pills, ["prefix", "name"])
        self.assertEqual(fresh.status, "Preset: Client snake")

    def test_cycling_a_preset_loads_its_name_and_drops_suggestions(self):
        session = self.session_for("notes.txt")
        session.set_name("Weekly Minutes")
        session.set_suffix("final")
        session.save_preset("Minutes")

        fresh = self.session_for("IMG 0001.txt")
        self.command(fresh, "s")
        self.command(fresh, "22")
        self.command(fresh, "e")
        self.assertEqual(fresh.new_name, "weekly-minutes-final.txt")

    def test_blank_preset_name_is_not_saved(self):
        session = self.session_for("notes.txt")
        self.assertFalse(session.save_preset("   "))

    def test_cycle_without_presets_says_so(self):
        session = self.session_for("notes.txt")
        self.command(session, "e")
        self.assertEqual(session.status, "No saved presets")


class SafePreviewTests(SessionTestCase):
    def test_preview_is_safe_when_no_item_has_a_problem(self):
        session = self.session_for("a.txt", "b.txt")
        self.assertTrue(session.safe)

    def test_two_items_with_the_same_result_make_the_preview_unsafe(self):
        session = self.session_for("a.txt", "b.txt")
        session.set_name("same")
        self.assertFalse(session.safe)


class RenameAndUndoTests(SessionTestCase):
    def test_enter_renames_the_files_and_asks_to_close(self):
        session = self.session_for("Quarterly Report.txt")
        self.assertTrue(session.key_down("Return"))
        self.assertTrue((self.files / "quarterly-report.txt").exists())
        self.assertEqual(session.take_requests(), [("close",)])

    def test_enter_in_command_mode_renames(self):
        session = self.session_for("Quarterly Report.txt")
        session.key_down("grave", "`")
        session.key_down("Return")
        self.assertTrue((self.files / "quarterly-report.txt").exists())
        session.key_up("grave")
        self.assertEqual(session.take_requests(), [("close",)])

    def test_undo_command_restores_the_original_name(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        renamed = RenameSession([str(self.files / "quarterly-report.txt")])
        self.command(renamed, "u")
        self.assertTrue((self.files / "Quarterly Report.txt").exists())

    def test_history_restore_undoes_one_rename(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        entries = session.history_entries()
        self.assertEqual([Path(current).name for current, _ in entries], ["quarterly-report.txt"])
        session.restore_from_history(entries[0][0])
        self.assertTrue((self.files / "Quarterly Report.txt").exists())

    def test_rename_applies_active_suggestions(self):
        session = self.session_for("IMG 0001.txt")
        self.command(session, "s")
        self.command(session, "22")
        session.key_down("Return")
        self.assertTrue((self.files / "img-0001.txt").exists())
        self.assertFalse((self.files / "img_0001.txt").exists())
        self.assertEqual(session.take_requests(), [("close",)])

    def test_rename_applies_the_rules_without_suggestions(self):
        session = self.session_for("IMG 0001.txt")
        self.command(session, "s")
        self.command(session, "22")
        self.command(session, "22x")
        session.key_down("Return")
        self.assertTrue((self.files / "img_0001.txt").exists())

    def test_enter_with_an_unsafe_preview_renames_nothing_and_shows_the_problem(self):
        session = self.session_for("a.txt", "b.txt")
        session.set_name("same")
        session.key_down("Return")
        self.assertTrue((self.files / "a.txt").exists())
        self.assertTrue((self.files / "b.txt").exists())
        self.assertEqual(session.status, "a.txt: More than one item would receive this name")
        self.assertEqual(session.take_requests(), [])

    def test_rows_with_a_problem_carry_its_text(self):
        session = self.session_for("a.txt", "b.txt")
        session.set_name("same")
        self.assertEqual(
            [(row["original"], row["problem"]) for row in session.rows],
            [("a.txt", "More than one item would receive this name"),
             ("b.txt", "More than one item would receive this name")],
        )
        session.set_name("")
        self.assertEqual([row["problem"] for row in session.rows], ["", ""])

    def test_existing_target_is_a_problem(self):
        session = self.session_for("notes.txt")
        (self.files / "taken.txt").write_text("x", encoding="utf-8")
        session.set_name("taken")
        self.assertEqual(session.rows[0]["problem"], "A file or folder with this name already exists")

    def test_vanished_source_blocks_the_rename_and_the_window_stays_open(self):
        session = self.session_for("Quarterly Report.txt")
        (self.files / "Quarterly Report.txt").unlink()
        session.rename()
        self.assertEqual(session.take_requests(), [])
        self.assertEqual(session.status, "Quarterly Report.txt: Source no longer exists")

    def test_failure_during_the_rename_is_shown_in_the_status_line(self):
        session = self.session_for("Quarterly Report.txt")
        with mock.patch("omni_session.execute", side_effect=failing_apply):
            session.rename()
        self.assertEqual(session.take_requests(), [])
        self.assertEqual(session.status, "Rename failed: Destination now exists")
        self.assertTrue((self.files / "Quarterly Report.txt").exists())

    def test_undo_without_history_says_so(self):
        session = self.session_for("notes.txt")
        self.command(session, "u")
        self.assertEqual(session.status, "Nothing to undo for these items")

    def test_undo_failure_is_shown(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        (self.files / "Quarterly Report.txt").write_text("in the way", encoding="utf-8")
        renamed = RenameSession([str(self.files / "quarterly-report.txt")])
        self.command(renamed, "u")
        self.assertEqual(renamed.status, "Undo failed: Cannot restore quarterly-report.txt: Quarterly Report.txt exists.")
        self.assertTrue((self.files / "quarterly-report.txt").exists())

    def test_undo_shows_the_restored_names_in_the_preview(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        renamed = RenameSession([str(self.files / "quarterly-report.txt")])
        self.command(renamed, "u")
        self.assertEqual(renamed.status, "Restored 1 item")
        self.assertEqual(renamed.original_name, "Quarterly Report.txt")
        self.assertTrue(renamed.safe)

    def test_history_restore_failure_is_shown(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        (self.files / "Quarterly Report.txt").write_text("in the way", encoding="utf-8")
        session.restore_from_history(str(self.files / "quarterly-report.txt"))
        self.assertTrue(session.status.startswith("Undo failed: Cannot restore"))

    def test_history_restore_shows_the_restored_name(self):
        session = self.session_for("Quarterly Report.txt")
        session.rename()
        renamed = RenameSession([str(self.files / "quarterly-report.txt")])
        renamed.restore_from_history(str(self.files / "quarterly-report.txt"))
        self.assertEqual(renamed.original_name, "Quarterly Report.txt")
        self.assertTrue(renamed.safe)

    def test_unreadable_presets_are_reported(self):
        session = self.session_for("notes.txt")
        presets = self.root / "config" / "OmniRename" / "presets.json"
        presets.parent.mkdir(parents=True)
        presets.write_text("{broken", encoding="utf-8")
        self.command(session, "e")
        self.assertEqual(session.status, "Presets unavailable: The preset file is unreadable.")

    def test_invalid_replacement_pattern_is_a_problem(self):
        session = self.session_for("notes.txt")
        session.set_find("notes")
        session.set_replace("\\")
        self.assertFalse(session.safe)
        self.assertTrue(session.rows[0]["problem"].startswith("Invalid regular expression"))
        session.key_down("Return")
        self.assertTrue((self.files / "notes.txt").exists())
        self.assertTrue(session.status.startswith("notes.txt: Invalid regular expression"))

    def test_bridge_error_during_preview_is_shown(self):
        session = self.session_for("notes.txt")
        with mock.patch("omni_session.execute", side_effect=ValueError("bad options")):
            session.set_name("x")
        self.assertFalse(session.safe)
        self.assertEqual(session.status, "Preview failed: bad options")


class CommandModeTests(SessionTestCase):
    def test_typing_without_command_mode_is_left_to_the_focused_field(self):
        session = self.session_for("notes.txt")
        self.assertFalse(session.key_down("s", "s"))

    def test_command_runs_on_release_of_backtick(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        session.key_down("s", "s")
        session.key_up("s")
        self.assertEqual(session.status, "⌁ Command: ` + s")
        self.assertEqual(session.new_name, "notes.txt")
        session.key_up("grave")
        self.assertEqual(session.status, "Style: snake_case")
        self.assertFalse(session.key_down("s", "s"))

    def test_held_backtick_auto_repeat_is_ignored(self):
        session = self.session_for("Quarterly Report.txt")
        for _ in range(4):
            self.assertTrue(session.key_down("grave", "`"))
        session.key_down("s", "s")
        for _ in range(3):
            session.key_down("grave", "`")
        session.key_up("s")
        session.key_up("grave")
        self.assertEqual(session.new_name, "quarterly_report.txt")
        self.assertEqual(session.status, "Style: snake_case")

    def test_key_held_down_while_backtick_is_held_counts_once(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        for _ in range(3):
            session.key_down("5", "5")
        session.key_up("5")
        self.assertEqual(session.status, "⌁ Command: ` + 5")
        session.key_up("grave")
        self.assertEqual(session.new_name, "notes-01.txt")

    def test_repeated_key_after_release_counts_again(self):
        session = self.session_for("IMG 0001.txt")
        self.command(session, "s")
        self.command(session, "22")
        self.assertEqual(session.status, "Contextual names suggested")

    def test_shifted_key_released_by_keycode_counts_once(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`", code=49)
        session.key_down("question", "?", code=61)
        session.key_down("question", "?", code=61)
        session.key_up("slash", code=61)
        session.key_down("question", "?", code=61)
        session.key_up("question", code=61)
        session.key_up("grave", code=49)
        self.assertEqual(session.status, "Unknown command: ??")

    def test_multi_key_codes_run_on_release(self):
        session = self.session_for("notes.txt")
        session.set_prefix("client")
        self.command(session, "4c2")
        self.assertEqual(session.new_name, "202403-client-notes.txt")
        self.command(session, "41")
        self.assertEqual(session.new_name, "202403-client-notes.txt")
        self.command(session, "14")
        self.assertEqual(session.new_name, "client-202403-notes.txt")
        self.command(session, "5c123")
        self.assertEqual(session.new_name, "client-202403-notes-001.txt")
        self.command(session, "22")
        self.command(session, "22x")
        self.assertEqual(session.status, "AI suggestion removed")

    def test_tapping_backtick_alone_inserts_a_literal_backtick(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        session.key_down("grave", "`")
        session.key_down("Shift_L")
        session.key_up("grave")
        self.assertEqual(session.take_requests(), [("insert_text", "`")])
        self.assertFalse(session.key_down("s", "s"))
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.status, "Press a pill to edit that part of the filename")

    def test_command_key_released_under_another_name_still_runs(self):
        session = self.session_for("notes.txt")
        session.key_down("dead_grave", "`", code=49)
        session.key_down("s", "s", code=39)
        session.key_up("s", code=39)
        session.key_up("asciitilde", code=49)
        self.assertEqual(session.status, "Style: snake_case")

    def test_unknown_command_changes_nothing(self):
        session = self.session_for("notes.txt")
        self.command(session, "zz")
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.status, "Unknown command: zz")
        self.assertEqual(session.take_requests(), [])

    def test_incomplete_command_changes_nothing(self):
        session = self.session_for("notes.txt")
        self.command(session, "5c1")
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.status, "Unknown command: 5c1")

    def test_focus_loss_cancels_the_command_without_running_it(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        session.key_down("s", "s")
        session.focus_lost()
        self.assertFalse(session.key_down("x", "x"))
        self.assertEqual(session.status, "Press a pill to edit that part of the filename")
        session.key_up("s")
        session.key_up("grave")
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.take_requests(), [])
        self.command(session, "s")
        self.assertEqual(session.status, "Style: snake_case")

    def test_arrows_in_command_mode_move_between_pills(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        session.key_down("Right")
        session.key_down("Left")
        session.key_down("Left")
        self.assertEqual(session.take_requests(), [("focus_step", 1), ("focus_step", -1), ("focus_step", -1)])
        session.key_up("grave")
        self.assertEqual(session.take_requests(), [])
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.status, "Press a pill to edit that part of the filename")

    def test_escape_in_command_mode_asks_to_revert(self):
        session = self.session_for("notes.txt")
        session.key_down("grave", "`")
        session.key_down("Escape")
        self.assertEqual(session.take_requests(), [("open", "confirm_revert")])
        self.assertFalse(session.key_down("s", "s"))
        session.key_down("grave", "`")
        session.key_up("grave")
        self.assertEqual(session.take_requests(), [])
        self.assertFalse(session.key_down("s", "s"))

    def test_cheat_sheet_command(self):
        session = self.session_for("notes.txt")
        self.command(session, "?")
        self.assertEqual(session.take_requests(), [("open", "shortcuts")])

    def test_cheat_sheet_shows_backtick_by_default(self):
        session = self.session_for("notes.txt")
        self.assertIn("` + S     Cycle filename style", session.cheat_sheet)

    def test_revert_clears_every_rule(self):
        session = self.session_for("notes.txt")
        self.command(session, "1")
        session.set_prefix("client")
        self.command(session, "4")
        self.command(session, "5")
        session.set_name("Other")
        session.revert()
        self.assertEqual(session.new_name, "notes.txt")
        self.assertEqual(session.visible_pills, ["name"])
        self.assertEqual(session.status, "Original name restored")


class CommandKeySettingTests(SessionTestCase):
    def write_settings(self, text):
        folder = self.root / "config" / "OmniRename"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "settings.json").write_text(text, encoding="utf-8")

    def test_configured_key_holds_command_mode(self):
        self.write_settings('{"command_key": "§"}')
        session = self.session_for("notes.txt")
        self.assertTrue(session.key_down("section", "§"))
        session.key_down("section", "§")
        session.key_down("s", "s")
        session.key_up("s")
        self.assertEqual(session.status, "⌁ Command: § + s")
        session.key_up("section")
        self.assertEqual(session.status, "Style: snake_case")

    def test_configured_key_tapped_alone_inserts_itself(self):
        self.write_settings('{"command_key": "§"}')
        session = self.session_for("notes.txt")
        session.key_down("section", "§")
        session.key_up("section")
        self.assertEqual(session.take_requests(), [("insert_text", "§")])

    def test_backtick_is_ordinary_text_when_another_key_is_configured(self):
        self.write_settings('{"command_key": "§"}')
        session = self.session_for("notes.txt")
        self.assertFalse(session.key_down("grave", "`"))
        self.assertFalse(session.key_down("dead_grave", "`"))
        session.key_up("grave")
        self.assertEqual(session.take_requests(), [])
        self.assertFalse(session.key_down("s", "s"))

    def test_configured_key_released_by_keycode_after_its_name_changes(self):
        self.write_settings('{"command_key": "#"}')
        session = self.session_for("notes.txt")
        session.key_down("numbersign", "#", code=51)
        session.key_down("4", "4", code=13)
        session.key_down("4", "4", code=13)
        session.key_up("4", code=13)
        session.key_up("apostrophe", code=51)
        self.assertEqual(session.new_name, "20240309-notes.txt")

    def test_non_ascii_letter_can_be_the_configured_key(self):
        self.write_settings('{"command_key": "ß"}')
        session = self.session_for("notes.txt")
        self.command_with(session, "ssharp", "ß", "s")
        self.assertEqual(session.status, "Style: snake_case")

    def command_with(self, session, key, char, code):
        session.key_down(key, char)
        for typed in code:
            session.key_down(typed, typed)
            session.key_up(typed)
        session.key_up(key)

    def test_cheat_sheet_shows_the_configured_key(self):
        self.write_settings('{"command_key": "§"}')
        session = self.session_for("notes.txt")
        self.assertIn("§ + S     Cycle filename style", session.cheat_sheet)
        self.assertNotIn("`", session.cheat_sheet)

    def test_invalid_settings_fall_back_to_backtick(self):
        for text in ("{not json", "[]", '{"command_key": 5}', '{"command_key": "ab"}',
                     '{"command_key": ""}', '{"command_key": " "}', '{"command_key": "s"}',
                     '{"command_key": "2"}', '{"command_key": "?"}', '{"other": "§"}'):
            with self.subTest(text=text):
                self.write_settings(text)
                session = self.session_for("Quarterly Report.txt")
                self.command(session, "s")
                self.assertEqual(session.new_name, "quarterly_report.txt")
                self.assertIn("` + S", session.cheat_sheet)

    def test_unreadable_settings_fall_back_to_backtick(self):
        (self.root / "config" / "OmniRename" / "settings.json").mkdir(parents=True)
        session = self.session_for("Quarterly Report.txt")
        self.command(session, "s")
        self.assertEqual(session.new_name, "quarterly_report.txt")


def failing_apply(command, payload):
    if command in ("apply", "apply-manual"):
        raise RenameError("Destination now exists")
    return execute(command, payload)


if __name__ == "__main__":
    unittest.main()
