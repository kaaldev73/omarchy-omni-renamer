"""Contextual F2 dispatcher for CaRe on Omarchy."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


FILE_MANAGERS = {"org.gnome.nautilus", "nautilus"}


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)


def active_class() -> str:
    try:
        return str(json.loads(run(["hyprctl", "activewindow", "-j"]).stdout).get("class", "")).lower()
    except (json.JSONDecodeError, subprocess.SubprocessError):
        return ""


def selected_paths() -> list[str]:
    run(["wtype", "-M", "ctrl", "c", "-m", "ctrl"])
    time.sleep(0.15)
    result = run(["wl-paste", "--no-newline", "--type", "text/uri-list"])
    paths = []
    for line in result.stdout.splitlines():
        value = line.strip()
        if value.startswith("file://"):
            from urllib.parse import unquote, urlparse

            path = unquote(urlparse(value).path)
            if path:
                paths.append(path)
    return paths


def forward_f2() -> None:
    subprocess.Popen(["wtype", "-k", "F2"])


def main() -> int:
    if active_class() not in FILE_MANAGERS:
        forward_f2()
        return 0
    paths = selected_paths()
    if not paths:
        forward_f2()
        return 0
    payload = json.dumps({"paths": paths}, ensure_ascii=False)
    plugin_dir = Path(__file__).resolve().parent
    subprocess.Popen(["python", str(plugin_dir / "omni_gtk.py"), payload])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
