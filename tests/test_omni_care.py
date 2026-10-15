import json
import tempfile
import unittest
from pathlib import Path

import omni_care
from care_core import RenameError


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
            omni_care.rename([first, second], "kebab-case", [], ["1"], self.history)

        self.assertIn("More than one item would receive this name", str(raised.exception))
        self.assertEqual(sorted(p.name for p in self.folder.glob("*.txt")), ["Report.txt", "report.txt"])
        self.assertEqual(first.read_text(), "A")
        self.assertEqual(second.read_text(), "B")

    def test_an_existing_name_renames_nothing(self):
        source = self.make("Report.txt", "A")
        self.make("report-1.txt", "B")

        with self.assertRaises(RenameError) as raised:
            omni_care.rename([source], "kebab-case", [], ["1"], self.history)

        self.assertIn("already exists", str(raised.exception))
        self.assertEqual(source.read_text(), "A")
        self.assertEqual((self.folder / "report-1.txt").read_text(), "B")

    def test_undo_restores_what_rename_changed(self):
        source = self.make("My Report.txt", "A")

        moves = omni_care.rename([source], "kebab-case", [], [], self.history)
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
