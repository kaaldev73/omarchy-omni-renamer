import tempfile
import unittest
from pathlib import Path

from care_presets import PresetStore


class PresetStoreTests(unittest.TestCase):
    def test_named_preset_round_trip_and_sorted_listing(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "presets.json")
            store.save("Photos", {"case_style": "kebab-case", "counter_start": 1})
            store.save("Archive", {"date_day": True})

            self.assertEqual(store.names(), ["Archive", "Photos"])
            self.assertEqual(store.load("Photos")["counter_start"], 1)

    def test_saving_same_name_updates_preset(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "presets.json")
            store.save("Work", {"prefix": "draft"})
            store.save("Work", {"prefix": "final"})
            self.assertEqual(store.load("Work"), {"prefix": "final"})

    def test_invalid_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PresetStore(Path(directory) / "presets.json")
            with self.assertRaisesRegex(ValueError, "Preset name"):
                store.save("\n", {})

    def test_corrupt_file_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presets.json"
            path.write_text("broken", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unreadable"):
                PresetStore(path).names()


if __name__ == "__main__":
    unittest.main()
