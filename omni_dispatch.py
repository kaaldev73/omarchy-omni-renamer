"""Contextual Alt+S dispatcher for OmniRename on Omarchy."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


FILE_MANAGERS = {"org.gnome.nautilus", "nautilus"}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)


def active_window() -> tuple[str, str]:
    """The focused window's class (lower-cased) and its Hyprland address."""
    try:
        window = json.loads(run(["hyprctl", "activewindow", "-j"]).stdout)
    except (json.JSONDecodeError, subprocess.SubprocessError):
        return "", ""
    return str(window.get("class", "")).lower(), str(window.get("address", ""))


def send_shortcut(mods: str, key: str, address: str) -> None:
    """Send keys straight to one window with exactly these modifiers.

    Alt is still held down while Alt+S runs this script, so simulated typing would
    reach the window as Ctrl+Alt+C; sending to the window directly avoids that and
    never triggers the Alt+S binding again.
    """
    run(["hyprctl", "dispatch",
         f'hl.dsp.send_shortcut({{mods="{mods}", key="{key}", window="address:{address}"}})'])


def selected_paths(address: str) -> list[str]:
    # Empty the clipboard first so an earlier copy is never taken for the selection
    run(["wl-copy", "--clear"])
    send_shortcut("CTRL", "C", address)
    for _ in range(10):
        time.sleep(0.1)
        result = run(["wl-paste", "--no-newline", "--type", "text/uri-list"])
        paths = [
            unquote(urlparse(line.strip()).path)
            for line in result.stdout.splitlines()
            if line.strip().startswith("file://")
        ]
        if paths:
            return paths
    return []


def main() -> int:
    window_class, address = active_window()
    if window_class not in FILE_MANAGERS:
        send_shortcut("ALT", "S", address)
        return 0
    paths = selected_paths(address)
    if not paths:
        return 0
    plugin_dir = Path(__file__).resolve().parent
    subprocess.Popen(["python", str(plugin_dir / "omni_care.py"), *paths])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
