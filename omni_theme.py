"""The Omarchy theme's colours as the palette OmniRename's stylesheet uses.

Pure: no GTK. The palette recolours libadwaita's own CSS variables, so stock
widgets and every dialog follow the theme. A role the theme does not provide
keeps Adwaita's colour.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

THEME_FILE = Path.home() / ".local/state/omarchy/current/theme/colors.toml"

# Palette role -> the colors.toml key it comes from. Muted text uses
# dark_foreground: the theme's own "muted" is too faint to read as text.
THEME_KEYS = {
    "background": "background",
    "surface": "lighter_background",
    "foreground": "foreground",
    "muted": "dark_foreground",
    "accent": "accent",
    "error": "red",
    "selection": "selection",
}

# Palette role -> Adwaita's colour for it, used when the theme lacks the role.
ADWAITA = {
    "background": "var(--window-bg-color)",
    "surface": "var(--view-bg-color)",
    "foreground": "var(--window-fg-color)",
    "muted": "color-mix(in srgb, var(--window-fg-color) 55%, transparent)",
    "accent": "var(--accent-color)",
    "error": "var(--error-color)",
    "selection": "color-mix(in srgb, var(--accent-bg-color) 30%, transparent)",
}

# Palette role -> the Adwaita variables a themed role overrides.
OVERRIDES = {
    "background": ("--window-bg-color", "--dialog-bg-color"),
    "surface": ("--view-bg-color", "--card-bg-color", "--popover-bg-color"),
    "foreground": ("--window-fg-color", "--view-fg-color", "--dialog-fg-color"),
    "accent": ("--accent-color", "--accent-bg-color"),
    "error": ("--error-color", "--error-bg-color"),
}

HEX_COLOUR = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")


@dataclass(frozen=True)
class Theme:
    palette: dict[str, str]
    themed: frozenset[str]  # the roles the theme provides; the rest keep Adwaita's colour
    mode: str | None  # "light", "dark", or None to keep Adwaita's choice


def read_theme(text: str | None) -> Theme:
    """Turn the text of colors.toml (None when there is no file) into a Theme."""
    try:
        values = tomllib.loads(text) if text is not None else {}
    except tomllib.TOMLDecodeError:
        values = {}
    palette = {}
    for role, key in THEME_KEYS.items():
        value = values.get(key)
        valid = isinstance(value, str) and HEX_COLOUR.fullmatch(value)
        palette[role] = value if valid else ADWAITA[role]
    mode = values.get("mode")
    themed = frozenset(role for role in palette if palette[role] != ADWAITA[role])
    return Theme(palette, themed, mode if mode in ("light", "dark") else None)


def load_theme(path: Path = THEME_FILE) -> Theme:
    """Read the current Omarchy theme, so a newly switched theme shows on the next F2."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = None
    return read_theme(text)


def theme_css(theme: Theme) -> str:
    """The CSS variables for a Theme: --omni-<role> for every role, plus Adwaita overrides for themed roles."""
    lines = [f"  --omni-{role}: {value};" for role, value in theme.palette.items()]
    for role, variables in OVERRIDES.items():
        if role in theme.themed:
            lines += [f"  {variable}: {theme.palette[role]};" for variable in variables]
    return ":root {\n" + "\n".join(lines) + "\n}\n"
