import re
import unittest
from pathlib import Path


class OverlayLayoutTests(unittest.TestCase):
    def test_outer_card_has_room_for_all_rename_controls(self):
        qml = Path("OmniRename.qml").read_text(encoding="utf-8")
        width = re.search(r"width: Math\.min\((\d+), panel\.width", qml)
        height = re.search(r"height: Math\.min\((\d+), panel\.height", qml)
        self.assertIsNotNone(width)
        self.assertIsNotNone(height)
        self.assertGreaterEqual(int(width.group(1)), 900)
        self.assertGreaterEqual(int(height.group(1)), 700)
        self.assertIn("radius: Math.max(20, Style.cornerRadius)", qml)
        self.assertIn("clip: true", qml)

    def test_preview_rows_use_explicit_readable_surfaces(self):
        qml = Path("OmniRename.qml").read_text(encoding="utf-8")
        self.assertIn('objectName: "previewRow"', qml)
        self.assertIn('objectName: "originalName"', qml)
        self.assertIn('objectName: "renameInput"', qml)
        self.assertIn('objectName: "renameStatus"', qml)
        self.assertIn("height: Math.max(44, Style.space(30))", qml)

    def test_all_date_formats_have_room_and_clear_labels(self):
        qml = Path("OmniRename.qml").read_text(encoding="utf-8")
        self.assertIn('id: dateOptions', qml)
        self.assertIn("Layout.columnSpan: 3", qml)
        for label in ("YYYYMMDD", "YYYYMM", "YYYY"):
            self.assertIn(f'text: "{label}"', qml)

    def test_preset_person_guide_and_tooltip_controls_are_present(self):
        qml = Path("OmniRename.qml").read_text(encoding="utf-8")
        self.assertIn('id: presetName', qml)
        self.assertIn('text: "Save preset"', qml)
        self.assertIn('text: "Load"', qml)
        self.assertIn('id: personField', qml)
        self.assertIn('id: namingGuide', qml)
        self.assertIn('ToolTip.text: "Increase each following number by this amount. Example: step 5 gives 1, 6, 11."', qml)


if __name__ == "__main__":
    unittest.main()
