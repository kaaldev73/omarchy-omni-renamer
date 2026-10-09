import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from care_core import (
    NamingOptions,
    RenameHistory,
    RenameError,
    RenameTransaction,
    build_rename_plan,
    build_manual_plan,
    date_prefixes,
    transform_filename,
)


class NamingTests(unittest.TestCase):
    def test_case_conversion_preserves_extension(self):
        options = NamingOptions(case_style="kebab-case")
        self.assertEqual(
            transform_filename("FinalReport2023.PDF", options),
            "final-report-2023.PDF",
        )

    def test_prefixes_and_suffixes_are_composed(self):
        options = NamingOptions(
            case_style="snake_case",
            prefixes=("20260905",),
            suffixes=("v2", "AC"),
        )
        self.assertEqual(
            transform_filename("Client Data.csv", options),
            "20260905_client_data_v2_AC.csv",
        )

    def test_multi_part_extension_is_preserved(self):
        options = NamingOptions(case_style="lowercase")
        self.assertEqual(
            transform_filename("Project Archive.TAR.GZ", options),
            "project archive.TAR.GZ",
        )

    def test_unicode_words_are_preserved(self):
        options = NamingOptions(case_style="kebab-case")
        self.assertEqual(transform_filename("Café Menu.pdf", options), "café-menu.pdf")

    def test_windows_control_characters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "control character"):
            transform_filename(
                "name.txt", NamingOptions(prefixes=("bad\x01prefix",))
            )

    def test_date_prefixes_are_generated(self):
        self.assertEqual(
            date_prefixes(date(2026, 9, 5), ("yyyymmdd", "yyyy")),
            ("20260905", "2026"),
        )

    def test_find_replace_regex_trim_and_counter_pipeline(self):
        options = NamingOptions(
            case_style="kebab-case",
            find=r"report[-_ ]?(\d+)",
            replace=r"summary \1",
            use_regex=True,
            prefixes=("client",),
            counter_start=7,
            counter_padding=3,
            trim_start=1,
        )
        self.assertEqual(
            transform_filename("xReport-42.PDF", options, index=2),
            "client-summary-42-009.PDF",
        )

    def test_person_name_can_be_added_before_or_after_the_base_name(self):
        before = NamingOptions(person="Ada Lovelace", person_position="prefix")
        after = NamingOptions(person="Ada Lovelace", person_position="suffix")
        self.assertEqual(transform_filename("Project Notes.md", before), "Ada Lovelace-project-notes.md")
        self.assertEqual(transform_filename("Project Notes.md", after), "project-notes-Ada Lovelace.md")

    def test_explicit_name_replaces_the_base_name(self):
        self.assertEqual(transform_filename("old-file.txt", NamingOptions(name="Quarterly Report")), "quarterly-report.txt")

    def test_number_can_be_ordered_before_suffix(self):
        options = NamingOptions(name="report", suffixes=("final",), counter_start=1, counter_position="before_suffix")
        self.assertEqual(transform_filename("old.txt", options), "report-01-final.txt")


class PlanningTests(unittest.TestCase):
    def test_manual_agent_names_receive_normal_collision_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "second.txt"
            first.touch()
            second.touch()
            plan = build_manual_plan(((first, "same.txt"), (second, "same.txt")))
            self.assertFalse(plan.is_safe)

    def test_dotted_folder_name_has_no_file_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "My.Project"
            folder.mkdir()
            plan = build_rename_plan([folder], NamingOptions(case_style="kebab-case"))
            self.assertEqual(plan.items[0].destination.name, "my-project")

    def test_existing_destination_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "My File.txt"
            source.write_text("source", encoding="utf-8")
            (root / "my-file.txt").write_text("existing", encoding="utf-8")

            plan = build_rename_plan(
                [source], NamingOptions(case_style="kebab-case")
            )

            self.assertFalse(plan.is_safe)
            self.assertIn("already exists", plan.items[0].problem)

    def test_two_sources_cannot_share_a_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "A B.txt"
            second = root / "a_b.txt"
            first.touch()
            second.touch()

            plan = build_rename_plan(
                [first, second], NamingOptions(case_style="kebab-case")
            )

            self.assertFalse(plan.is_safe)


class TransactionTests(unittest.TestCase):
    def test_apply_and_undo_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Annual Report.pdf"
            source.write_text("report", encoding="utf-8")
            history = RenameHistory(root / "history.json")
            plan = build_rename_plan(
                [source], NamingOptions(case_style="kebab-case")
            )

            renamed = RenameTransaction(history).apply(plan)
            destination = root / "annual-report.pdf"
            self.assertEqual(renamed, [destination])
            self.assertTrue(destination.exists())

            restored = RenameTransaction(history).undo([destination])
            self.assertEqual(restored, [source])
            self.assertTrue(source.exists())
            self.assertEqual(json.loads((root / "history.json").read_text())["renames"], {})

    def test_plan_is_revalidated_before_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "My File.txt"
            source.write_text("source", encoding="utf-8")
            plan = build_rename_plan([source], NamingOptions())
            destination = root / "my-file.txt"
            destination.write_text("do not replace", encoding="utf-8")

            with self.assertRaisesRegex(RenameError, "Destination now exists"):
                RenameTransaction(RenameHistory(root / "history.json")).apply(plan)

            self.assertEqual(source.read_text(encoding="utf-8"), "source")
            self.assertEqual(destination.read_text(encoding="utf-8"), "do not replace")

    def test_undo_refuses_to_replace_an_existing_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            renamed = root / "report.txt"
            original = root / "Report.txt"
            renamed.write_text("renamed", encoding="utf-8")
            original.write_text("existing", encoding="utf-8")
            history = RenameHistory(root / "history.json")
            history.save({str(renamed): str(original)})

            with self.assertRaisesRegex(RenameError, "exists"):
                RenameTransaction(history).undo([renamed])

    def test_corrupt_history_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text("not-json", encoding="utf-8")
            with self.assertRaisesRegex(RenameError, "unreadable"):
                RenameHistory(path).load()

    def test_incomplete_rollback_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "First File.txt"
            second = root / "Second File.txt"
            first.touch()
            second.touch()
            plan = build_rename_plan([first, second], NamingOptions())
            original_rename = Path.rename
            calls = 0

            def unreliable_rename(path, target):
                nonlocal calls
                calls += 1
                if calls in (2, 3):
                    raise OSError("injected failure")
                return original_rename(path, target)

            with mock.patch.object(Path, "rename", autospec=True, side_effect=unreliable_rename):
                with self.assertRaisesRegex(RenameError, "rollback is incomplete"):
                    RenameTransaction(RenameHistory(root / "history.json")).apply(plan)


if __name__ == "__main__":
    unittest.main()
