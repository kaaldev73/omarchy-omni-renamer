"""The current Omarchy theme's colours as the palette the OmniRename window draws with."""

import re
import tomllib
from pathlib import Path

THEME_FILE = Path.home() / ".local/state/omarchy/current/theme/colors.toml"

# Palette role -> the colors.toml key it comes from
THEME_KEYS = {
    "background": "background",
    "surface": "lighter_background",
    "foreground": "foreground",
    "muted": "dark_foreground",
    "accent": "accent",
    "success": "green",
    "error": "red",
}

# Used for any role the theme does not provide
FALLBACK = {
    "background": "#1e1e2e",
    "surface": "#2a2b3d",
    "foreground": "#cdd6f4",
    "muted": "#7f849c",
    "accent": "#89b4fa",
    "success": "#a6e3a1",
    "error": "#f38ba8",
}

HEX_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


def read_palette(text):
    """Turn the text of colors.toml (None when there is no file) into a palette."""
    try:
        colours = tomllib.loads(text) if text else {}
    except tomllib.TOMLDecodeError:
        colours = {}
    palette = {}
    for role, key in THEME_KEYS.items():
        colour = colours.get(key)
        palette[role] = colour if isinstance(colour, str) and HEX_COLOUR.match(colour) else FALLBACK[role]
    return palette


def load_palette(path=THEME_FILE):
    try:
        return read_palette(path.read_text(encoding="utf-8"))
    except OSError:
        return read_palette(None)


def mix(colour, other, amount):
    """Blend amount (0 to 1) of other into colour."""
    channels = [
        round(int(colour[i:i + 2], 16) * (1 - amount) + int(other[i:i + 2], 16) * amount)
        for i in (1, 3, 5)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)
