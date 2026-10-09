#!/usr/bin/env python3
"""PROTOTYPE, throwaway: which Omarchy theme colours should the GTK window use?

Four colour variants on the real OmniRename window, switchable from a floating
bar at the bottom, across every installed Omarchy theme plus "(no theme file)"
to see the Adwaita fallback.

Run:  python theme_prototype.py [variant A-D] [theme-name]

Renames only touch copies of mock_files_to_test in a scratch temp directory.
Lives on the prototype/theme-colours branch; never merge it into master.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACTIVE_THEME = Path.home() / ".local/state/omarchy/current/theme"
THEME_ROOTS = [Path("/usr/share/omarchy/themes"), Path.home() / ".config/omarchy/themes"]
NO_THEME = "(no theme file)"

# Each role falls back to this Adwaita CSS variable when the theme lacks its key.
ADWAITA = {
    "background": "var(--window-bg-color)",
    "surface": "var(--view-bg-color)",
    "foreground": "var(--window-fg-color)",
    "muted": "color-mix(in srgb, var(--window-fg-color) 55%, transparent)",
    "accent": "var(--accent-color)",
    "error": "var(--error-color)",
    "selection": "color-mix(in srgb, var(--accent-bg-color) 30%, transparent)",
    "prefix": "var(--blue-2)",
    "suffix": "var(--purple-2)",
    "date": "var(--yellow-3)",
    "number": "var(--green-3)",
}

COMMON_CSS = """
.prototype-hidden { opacity: 0; }
"""

VARIANTS = [
    {
        "key": "A",
        "name": "Outlined accent",
        "roles": {
            "background": "background",
            "surface": "lighter_background",
            "foreground": "foreground",
            "muted": "muted",
            "accent": "accent",
            "error": "red",
            "selection": "selection",
        },
        "css": """
.omni-window { background-color: var(--omni-background); color: var(--omni-foreground); }
.old-name { color: var(--omni-muted); font-size: 15px; }
.new-name { color: var(--omni-accent); font-size: 34px; font-weight: 600; }
.pill, .pill-entry { background: transparent; color: var(--omni-foreground); border: 2px solid var(--omni-accent);
  border-radius: 999px; padding: 6px 16px; box-shadow: none; outline: none; }
.pill-entry:focus-within { background: var(--omni-selection); }
.status { color: var(--omni-muted); }
.preview-list { background: transparent; }
.preview-list row { color: var(--omni-foreground); padding: 4px 8px; border-radius: 8px; }
.preview-list row:hover { background: var(--omni-selection); }
.preview-list row.problem { color: var(--omni-error); }
""",
    },
    {
        "key": "B",
        "name": "Filled surfaces",
        "roles": {
            "background": "dark_background",
            "surface": "lighter_background",
            "foreground": "bright_foreground",
            "muted": "dark_foreground",
            "accent": "accent",
            "error": "red",
            "selection": "selection",
        },
        "css": """
.omni-window { background-color: var(--omni-background); color: var(--omni-foreground); }
.old-name { color: var(--omni-muted); font-size: 13px; letter-spacing: 1px; }
.pill, .pill-entry { background: var(--omni-surface); color: var(--omni-foreground); border: none;
  border-radius: 8px; padding: 8px 14px; box-shadow: none; outline: none; }
.pill-entry:focus-within { background: var(--omni-accent); color: var(--omni-background); }
.new-name { color: var(--omni-foreground); font-size: 34px; font-weight: 700;
  border-bottom: 3px solid var(--omni-accent); padding-bottom: 4px; }
.status { color: var(--omni-accent); }
.preview-list { background: var(--omni-surface); border-radius: 10px; padding: 4px; }
.preview-list row { color: var(--omni-foreground); padding: 4px 10px; }
.preview-list row:hover { background: var(--omni-selection); }
.preview-list row.problem { background: color-mix(in srgb, var(--omni-error) 18%, transparent);
  border-left: 3px solid var(--omni-error); }
""",
    },
    {
        "key": "C",
        "name": "Coloured Name Parts",
        "roles": {
            "background": "background",
            "surface": "lighter_background",
            "foreground": "foreground",
            "muted": "dark_foreground",
            "accent": "accent",
            "error": "bright_red",
            "selection": "selection",
            "prefix": "cyan",
            "suffix": "magenta",
            "date": "yellow",
            "number": "green",
        },
        "css": """
.omni-window { background-color: var(--omni-background); color: var(--omni-foreground); }
.old-name { color: var(--omni-muted); font-family: monospace; }
.pill, .pill-entry { background: transparent; border: none; border-bottom: 3px solid currentColor;
  border-radius: 0; padding: 4px 6px; box-shadow: none; outline: none; }
.part-prefix { color: var(--omni-prefix); }
.part-name { color: var(--omni-accent); }
.part-suffix { color: var(--omni-suffix); }
.part-date { color: var(--omni-date); }
.part-number { color: var(--omni-number); }
.new-name { color: var(--omni-accent); font-size: 30px; font-family: monospace; }
.status { color: var(--omni-muted); font-family: monospace; }
.preview-list { background: transparent; }
.preview-list row { color: var(--omni-foreground); font-family: monospace; padding: 2px 6px; }
.preview-list row:hover { background: var(--omni-selection); }
.preview-list row.problem { color: var(--omni-error); font-weight: bold; }
""",
    },
    {
        "key": "D",
        "name": "Recolour Adwaita",
        "roles": {
            "background": "background",
            "surface": "lighter_background",
            "foreground": "foreground",
            "muted": "dark_foreground",
            "accent": "accent",
            "error": "red",
            "selection": "selection",
        },
        # Overrides libadwaita's own variables, so stock widgets and dialogs follow the theme.
        "css": """
:root {
  --window-bg-color: var(--omni-background); --window-fg-color: var(--omni-foreground);
  --view-bg-color: var(--omni-surface); --view-fg-color: var(--omni-foreground);
  --dialog-bg-color: var(--omni-background); --dialog-fg-color: var(--omni-foreground);
  --card-bg-color: var(--omni-surface); --popover-bg-color: var(--omni-surface);
  --accent-bg-color: var(--omni-accent); --accent-color: var(--omni-accent);
  --error-color: var(--omni-error); --error-bg-color: var(--omni-error);
}
.pill, .pill-entry { border: none; }
.old-name { color: var(--omni-muted); }
.new-name { color: var(--accent-color); font-size: 32px; font-weight: 600; }
.status { color: var(--omni-muted); }
.preview-list { border-radius: 10px; }
.preview-list row.problem { color: var(--error-color); }
""",
    },
]

BAR_CSS = """
.proto-bar { background: #111; color: #fff; border-radius: 999px; padding: 6px 12px; margin: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,.5); font-size: 12px; }
.proto-bar button { background: #333; color: #fff; border: none; border-radius: 999px; min-height: 24px;
  padding: 0 10px; box-shadow: none; }
.proto-bar label { color: #fff; }
"""


def theme_choices() -> list[tuple[str, Path | None]]:
    choices = [("active: " + read_name(), ACTIVE_THEME / "colors.toml")]
    for root in THEME_ROOTS:
        for theme in sorted(root.glob("*/colors.toml")):
            choices.append((theme.parent.name, theme))
    choices.append((NO_THEME, None))
    return choices


def read_name() -> str:
    try:
        return (ACTIVE_THEME.parent / "theme.name").read_text().strip()
    except OSError:
        return "?"


def read_theme(path: Path | None) -> dict:
    try:
        return tomllib.loads(path.read_text()) if path else {}
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def resolve(variant: dict, theme: dict) -> dict[str, tuple[str, str]]:
    """Map each role to (css value, where it came from)."""
    palette = {}
    for role, fallback in ADWAITA.items():
        key = variant["roles"].get(role)
        value = theme.get(key) if key else None
        if isinstance(value, str) and value.startswith("#"):
            palette[role] = (value, key)
        else:
            palette[role] = (fallback, "Adwaita" + (f" (no {key})" if key else ""))
    return palette


def install(app, root) -> None:
    """Mount the variant switcher on the real window. Called from omni_gtk when prototyping."""
    from gi.repository import Adw, Gdk, Gtk

    themes = theme_choices()
    state = {
        "variant": next((i for i, v in enumerate(VARIANTS) if v["key"] == os.environ.get("OMNI_THEME_VARIANT", "A")), 0),
        "theme": next((i for i, (name, _) in enumerate(themes) if name == os.environ.get("OMNI_THEME")), 0),
    }

    # Show every Name Part so each Pill colour is visible, and the target layout (no title, status line, list).
    session = app.session
    session.prefix = "draft"
    session.prefix_shown = True
    session.suffix = "v2"
    session.suffix_shown = True
    session.options["prefixes"] = ["draft"]
    session.options["suffixes"] = ["v2"]
    session.set_date("%Y%m%d", True)
    session.set_number(True)
    session.status = "Command: ` + 4   (status line)"
    for widget, part in (
        (app.prefix_entry, "prefix"),
        (app.name_entry, "name"),
        (app.suffix_entry, "suffix"),
        (app.date_button, "date"),
        (app.number_button, "number"),
    ):
        widget.add_css_class("part-" + part)
        widget.set_visible(True)
    child = root.get_first_child()
    while child is not None:
        if child.has_css_class("title-1"):
            child.set_visible(False)
        child = child.get_next_sibling()
    app.win.add_css_class("omni-window")
    root.set_margin_bottom(64)
    app.win.set_default_size(820, 560)
    app.detail.add_css_class("status")
    app.editor.set_visible(True)
    app.list.add_css_class("preview-list")
    app.list.set_visible(True)
    scroller = Gtk.ScrolledWindow(vexpand=True)
    root.remove(app.list)
    scroller.set_child(app.list)
    root.append(scroller)

    real_sync = app.sync

    def sync_with_problem_row():
        real_sync()
        app.editor.set_visible(True)
        app.list.prepend(Gtk.Label(label="sample-problem.txt  →  draft-report  (Problem: duplicate target name)", xalign=0))
        app.list.get_first_child().add_css_class("problem")

    app.sync = sync_with_problem_row

    provider = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    bar_provider = Gtk.CssProvider()
    bar_provider.load_from_string(BAR_CSS)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), bar_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)

    label = Gtk.Label()

    def apply():
        variant = VARIANTS[state["variant"]]
        theme_name, theme_path = themes[state["theme"]]
        theme = read_theme(theme_path)
        palette = resolve(variant, theme)
        variables = "".join(f"  --omni-{role}: {value};\n" for role, (value, _) in palette.items())
        provider.load_from_string(":root {\n" + variables + "}\n" + COMMON_CSS + variant["css"])
        mode = theme.get("mode")
        scheme = {"light": Adw.ColorScheme.FORCE_LIGHT, "dark": Adw.ColorScheme.FORCE_DARK}.get(mode, Adw.ColorScheme.DEFAULT)
        Adw.StyleManager.get_default().set_color_scheme(scheme)
        label.set_text(f"{variant['key']} ({variant['name']})   ·   theme: {theme_name}  [{state['theme'] + 1}/{len(themes)}]")
        print(f"\n== Variant {variant['key']} ({variant['name']}) · theme {theme_name} · mode {mode or 'Adwaita default'}")
        for role, (value, source) in palette.items():
            if role in variant["roles"] or source == "Adwaita":
                print(f"   {role:<11} {value:<70} <- {source}")

    def step(which: str, amount: int, count: int):
        state[which] = (state[which] + amount) % count
        apply()

    bar = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
    bar.add_css_class("proto-bar")
    for text, which, amount, count in (
        ("◀ variant", "variant", -1, len(VARIANTS)),
        ("variant ▶", "variant", 1, len(VARIANTS)),
    ):
        button = Gtk.Button(label=text, focusable=False)
        button.connect("clicked", lambda _b, w=which, a=amount, c=count: step(w, a, c))
        bar.append(button)
    bar.append(label)
    for text, which, amount, count in (
        ("◀ theme", "theme", -1, len(themes)),
        ("theme ▶", "theme", 1, len(themes)),
    ):
        button = Gtk.Button(label=text, focusable=False)
        button.connect("clicked", lambda _b, w=which, a=amount, c=count: step(w, a, c))
        bar.append(button)
    dialog = Gtk.Button(label="cheat sheet", focusable=False)
    dialog.connect("clicked", lambda _b: app.show_shortcuts())
    bar.append(dialog)

    overlay = Gtk.Overlay()
    app.win.set_content(overlay)
    overlay.set_child(root)
    overlay.add_overlay(bar)
    apply()
    app.sync()


def main() -> int:
    scratch = Path(tempfile.gettempdir()) / "omni-theme-prototype-wipe-me"
    shutil.rmtree(scratch, ignore_errors=True)
    shutil.copytree(HERE / "mock_files_to_test", scratch)
    env = dict(os.environ, OMNI_THEME_PROTOTYPE="1")
    if len(sys.argv) > 1:
        env["OMNI_THEME_VARIANT"] = sys.argv[1].upper()
    if len(sys.argv) > 2:
        env["OMNI_THEME"] = sys.argv[2]
    payload = json.dumps({"paths": [str(path) for path in sorted(scratch.iterdir())]})
    return subprocess.call([sys.executable, str(HERE / "omni_gtk.py"), payload], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
