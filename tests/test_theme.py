import re
import tempfile
import unittest
from pathlib import Path

from omni_theme import ADWAITA, load_theme, read_theme, theme_css

ROOT = Path(__file__).resolve().parent.parent

FULL = """
mode = "dark"
accent = "#7aa2f7"
selection = "#292e42"
muted = "#414868"
background = "#1a1b26"
lighter_background = "#24283b"
foreground = "#a9b1d6"
dark_foreground = "#565f89"
red = "#f7768e"
"""


class PaletteTests(unittest.TestCase):
    def test_full_file_maps_every_role_from_its_theme_key(self):
        theme = read_theme(FULL)

        self.assertEqual(
            theme.palette,
            {
                "background": "#1a1b26",
                "surface": "#24283b",
                "foreground": "#a9b1d6",
                "muted": "#565f89",
                "accent": "#7aa2f7",
                "error": "#f7768e",
                "selection": "#292e42",
            },
        )
        self.assertEqual(theme.mode, "dark")

    def test_missing_file_falls_back_to_adwaita_for_every_role(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = load_theme(Path(directory) / "colors.toml")

        self.assertEqual(theme.palette, ADWAITA)
        self.assertIsNone(theme.mode)

    def test_malformed_toml_falls_back_to_adwaita(self):
        theme = read_theme('accent = "#7aa2f7"\nbackground = [unclosed')

        self.assertEqual(theme.palette, ADWAITA)
        self.assertIsNone(theme.mode)

    def test_missing_or_invalid_keys_fall_back_one_role_at_a_time(self):
        theme = read_theme('accent = "#7aa2f7"\nred = "not a colour"\nbackground = 12\nmode = "sepia"')

        self.assertEqual(theme.palette["accent"], "#7aa2f7")
        self.assertEqual(theme.themed, {"accent"})
        for role in ("background", "surface", "foreground", "muted", "error", "selection"):
            self.assertEqual(theme.palette[role], ADWAITA[role], role)
        self.assertIsNone(theme.mode)

    def test_file_is_read_from_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "colors.toml"
            path.write_text(FULL, encoding="utf-8")

            self.assertEqual(load_theme(path), read_theme(FULL))

    def test_light_mode_is_kept(self):
        self.assertEqual(read_theme('mode = "light"').mode, "light")


class ThemeCssTests(unittest.TestCase):
    def test_themed_roles_override_adwaita_variables(self):
        css = theme_css(read_theme(FULL))

        self.assertIn("--omni-muted: #565f89;", css)
        self.assertIn("--accent-color: #7aa2f7;", css)
        self.assertIn("--window-bg-color: #1a1b26;", css)
        self.assertIn("--dialog-bg-color: #1a1b26;", css)
        self.assertIn("--error-color: #f7768e;", css)

    def test_missing_roles_leave_adwaita_variables_alone(self):
        css = theme_css(read_theme('accent = "#7aa2f7"'))

        self.assertIn("--accent-color: #7aa2f7;", css)
        self.assertNotIn("--window-bg-color:", css)
        self.assertNotIn("--error-color:", css)
        self.assertIn(f"--omni-muted: {ADWAITA['muted']};", css)


class StylesheetTests(unittest.TestCase):
    def test_stylesheet_has_no_hard_coded_colours(self):
        stylesheet = (ROOT / "omni.css").read_text(encoding="utf-8")

        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", stylesheet))
        self.assertIsNone(re.search(r"\brgba?\(", stylesheet))


if __name__ == "__main__":
    unittest.main()
