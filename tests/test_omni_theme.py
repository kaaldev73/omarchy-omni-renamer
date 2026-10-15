import unittest

from omni_theme import FALLBACK, mix, read_palette

TOKYO_NIGHT = """
mode = "dark"
accent = "#7aa2f7"
background = "#1a1b26"
lighter_background = "#24283b"
foreground = "#a9b1d6"
dark_foreground = "#565f89"
red = "#f7768e"
green = "#9ece6a"
"""


class PaletteTests(unittest.TestCase):
    def test_the_omarchy_theme_colours_the_window(self):
        palette = read_palette(TOKYO_NIGHT)

        self.assertEqual(palette["background"], "#1a1b26")
        self.assertEqual(palette["surface"], "#24283b")
        self.assertEqual(palette["foreground"], "#a9b1d6")
        self.assertEqual(palette["muted"], "#565f89")
        self.assertEqual(palette["accent"], "#7aa2f7")
        self.assertEqual(palette["success"], "#9ece6a")
        self.assertEqual(palette["error"], "#f7768e")

    def test_no_theme_file_uses_the_fallback(self):
        self.assertEqual(read_palette(None), FALLBACK)

    def test_a_broken_theme_file_uses_the_fallback(self):
        self.assertEqual(read_palette('accent = "#7aa2f7'), FALLBACK)

    def test_a_missing_or_unusable_colour_falls_back_alone(self):
        palette = read_palette('accent = "blue"\nbackground = "#000000"')

        self.assertEqual(palette["accent"], FALLBACK["accent"])
        self.assertEqual(palette["background"], "#000000")

    def test_mix_blends_two_colours(self):
        self.assertEqual(mix("#ff0000", "#0000ff", 0.25), "#bf0040")


if __name__ == "__main__":
    unittest.main()
