import json
from datetime import date
import tempfile
import unittest
from pathlib import Path

import omni_care
from omni_renamer import RenameError
from name_parts import Choices


class RenameTests(unittest.TestCase):
    def setUp(self):
        self._temporary = tempfile.TemporaryDirectory()
        self.folder = Path(self._temporary.name)
        self.history = omni_care.CareHistory(self.folder / "state" / "rename_backlog.json")

    def tearDown(self):
        self._temporary.cleanup()

    def make(self, name, text=""):
        path = self.folder / name
        path.write_text(text)
        return path

    def test_names_that_collide_rename_nothing(self):
        first = self.make("Report.txt", "A")
        second = self.make("report.txt", "B")

        with self.assertRaises(RenameError) as raised:
            omni_care.rename([first, second], Choices(version="1"), self.history)

        self.assertIn("More than one item would receive this name", str(raised.exception))
        self.assertEqual(sorted(p.name for p in self.folder.glob("*.txt")), ["Report.txt", "report.txt"])
        self.assertEqual(first.read_text(), "A")
        self.assertEqual(second.read_text(), "B")

    def test_an_existing_name_renames_nothing(self):
        source = self.make("Report.txt", "A")
        self.make("report-v1.txt", "B")

        with self.assertRaises(RenameError) as raised:
            omni_care.rename([source], Choices(version="1"), self.history)

        self.assertIn("already exists", str(raised.exception))
        self.assertEqual(source.read_text(), "A")
        self.assertEqual((self.folder / "report-v1.txt").read_text(), "B")

    def test_undo_restores_what_rename_changed(self):
        source = self.make("My Report.txt", "A")

        moves = omni_care.rename([source], Choices("kebab-case"), self.history)
        renamed = self.folder / "my-report.txt"
        self.assertEqual(moves, {str(source): str(renamed)})

        restored = omni_care.undo([renamed], self.history)

        self.assertEqual(restored, {str(renamed): str(source)})
        self.assertEqual(source.read_text(), "A")
        self.assertFalse(renamed.exists())

    def test_undo_reads_history_written_by_the_old_care_app(self):
        renamed = self.make("my-report.txt", "A")
        original = self.folder / "My Report.txt"
        self.history.path.parent.mkdir()
        self.history.path.write_text(json.dumps({str(renamed): str(original)}))

        restored = omni_care.undo([renamed], self.history)

        self.assertEqual(restored, {str(renamed): str(original)})
        self.assertEqual(original.read_text(), "A")

    def test_unreadable_history_renames_nothing(self):
        source = self.make("My Report.txt", "A")
        self.history.path.parent.mkdir()
        self.history.path.write_text("not json")

        with self.assertRaises(RenameError):
            omni_care.rename([source], Choices("kebab-case"), self.history)

        self.assertEqual(source.read_text(), "A")
        self.assertFalse((self.folder / "my-report.txt").exists())

    def test_a_version_that_is_not_a_number_renames_nothing(self):
        source = self.make("Report.txt", "A")

        with self.assertRaises(RenameError) as raised:
            omni_care.rename([source], Choices(version="vabc"), self.history)

        self.assertIn("Version", str(raised.exception))
        self.assertEqual(source.read_text(), "A")

    def test_a_date_that_is_not_real_renames_nothing(self):
        source = self.make("Report.txt", "A")

        with self.assertRaises(RenameError) as raised:
            omni_care.rename([source], Choices(date="20261345"), self.history)

        self.assertIn("Date", str(raised.exception))
        self.assertEqual(source.read_text(), "A")

    def test_the_history_lists_every_earlier_name_newest_first(self):
        source = self.make("My Report.txt", "A")
        omni_care.rename([source], Choices("kebab-case"), self.history)
        renamed = self.folder / "my-report.txt"
        omni_care.rename([renamed], Choices("kebab-case", version="2"), self.history)
        newest = self.folder / "my-report-v2.txt"

        chain = omni_care.name_chain(newest, self.history.load())

        self.assertEqual(chain, [str(newest), str(renamed), str(source)])

    def test_restore_jumps_back_several_renames_at_once(self):
        source = self.make("My Report.txt", "A")
        omni_care.rename([source], Choices("kebab-case"), self.history)
        omni_care.rename([self.folder / "my-report.txt"], Choices(version="2"), self.history)
        newest = self.folder / "my-report-v2.txt"

        moves = omni_care.restore(newest, source, self.history)

        self.assertEqual(moves, {str(newest): str(source)})
        self.assertEqual(source.read_text(), "A")
        self.assertEqual(self.history.load(), {})

    def test_a_looping_history_ends_the_chain(self):
        chain = omni_care.name_chain("/a/x.txt", {"/a/x.txt": "/a/y.txt", "/a/y.txt": "/a/x.txt"})

        self.assertEqual(chain, ["/a/x.txt", "/a/y.txt"])


class ReportTests(unittest.TestCase):
    def test_one_rename_is_reported_in_full(self):
        report = omni_care.rename_report({"/a/My Report.txt": "/a/my-report.txt"})

        self.assertEqual(report, ("success", "Renamed My Report.txt → my-report.txt", []))

    def test_several_renames_are_counted_with_the_list_behind_show_all(self):
        report = omni_care.rename_report({"/a/A.txt": "/a/a.txt", "/a/B.txt": "/a/b.txt"})

        self.assertEqual(report, ("success", "Renamed 2 items", ["A.txt → a.txt", "B.txt → b.txt"]))

    def test_nothing_to_change_is_said_plainly(self):
        self.assertEqual(
            omni_care.rename_report({}), ("info", "Nothing to change: the names already look like this", [])
        )

    def test_a_single_problem_is_shown_in_full(self):
        report = omni_care.problem_report(RenameError("Nothing was renamed.\nVersion vabc is not a number"))

        self.assertEqual(report, ("error", "Nothing was renamed: Version vabc is not a number", []))

    def test_several_problems_are_counted_with_the_list_behind_show_all(self):
        report = omni_care.problem_report(RenameError("Nothing was renamed.\nfirst\nsecond"))

        self.assertEqual(report, ("error", "Nothing was renamed: 2 Problems", ["first", "second"]))

    def test_undo_is_reported_like_a_rename(self):
        self.assertEqual(
            omni_care.undo_report({"/a/a.txt": "/a/A.txt"}), ("success", "Restored A.txt", [])
        )
        self.assertEqual(
            omni_care.undo_report({}), ("info", "Nothing to undo for these items", [])
        )


class GuideTests(unittest.TestCase):
    def test_the_guide_shows_one_example_name_per_style(self):
        examples = dict(omni_care.guide_examples(date(2026, 10, 15)))

        self.assertEqual(len(examples), 8)
        self.assertEqual(examples["kebab-case"], "20261015-project-report-v2-KR.pdf")
        self.assertEqual(examples["snake_case"], "20261015_project_report_v2_KR.pdf")
        self.assertEqual(examples["PascalCase"], "20261015-ProjectReport-v2-KR.pdf")
