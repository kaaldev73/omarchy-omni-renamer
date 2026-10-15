import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from care_core import RenameError, RenameHistory, RenameTransaction, build_manual_plan


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

    def test_existing_destination_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "My File.txt"
            source.write_text("source", encoding="utf-8")
            (root / "my-file.txt").write_text("existing", encoding="utf-8")

            plan = build_manual_plan([(source, "my-file.txt")])

            self.assertFalse(plan.is_safe)
            self.assertIn("already exists", plan.items[0].problem)

class TransactionTests(unittest.TestCase):
    def test_apply_and_undo_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Annual Report.pdf"
            source.write_text("report", encoding="utf-8")
            history = RenameHistory(root / "history.json")
            plan = build_manual_plan([(source, "annual-report.pdf")])

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
            plan = build_manual_plan([(source, "my-file.txt")])
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
            plan = build_manual_plan([(first, "first-file.txt"), (second, "second-file.txt")])
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
