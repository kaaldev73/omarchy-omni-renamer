import json
import subprocess
import unittest
from unittest import mock

import omni_dispatch


class FakeDesktop:
    """Hyprland, the clipboard and the focused window, as the dispatcher sees them."""

    def __init__(self, window_class, selection=(), clipboard=(), copy_works=True):
        self.window_class = window_class
        self.selection = list(selection)
        self.clipboard = list(clipboard)
        self.copy_works = copy_works
        self.sent = []
        self.launched = []

    def run(self, command):
        output = ""
        if command[:2] == ["hyprctl", "activewindow"]:
            output = json.dumps({"class": self.window_class, "address": "0xabc"})
        elif command[:2] == ["hyprctl", "dispatch"]:
            self.sent.append(command[2])
            if 'key="C"' in command[2] and self.copy_works:
                self.clipboard = list(self.selection)
        elif command[:2] == ["wl-copy", "--clear"]:
            self.clipboard = []
        elif command[0] == "wl-paste":
            output = "\n".join(f"file://{path}" for path in self.clipboard)
        return subprocess.CompletedProcess(command, 0, output, "")

    def popen(self, command):
        self.launched.append(command)

    def press_alt_s(self):
        with (
            mock.patch.object(omni_dispatch, "run", self.run),
            mock.patch.object(omni_dispatch.subprocess, "Popen", self.popen),
            mock.patch.object(omni_dispatch.time, "sleep"),
        ):
            omni_dispatch.main()


class ShortcutTests(unittest.TestCase):
    def test_alt_s_outside_the_file_manager_is_sent_on_to_that_window(self):
        desktop = FakeDesktop("kitty")

        desktop.press_alt_s()

        self.assertEqual(desktop.launched, [])
        self.assertEqual(
            desktop.sent, ['hl.dsp.send_shortcut({mods="ALT", key="S", window="address:0xabc"})']
        )

    def test_alt_s_in_the_file_manager_opens_the_window_on_the_selection(self):
        desktop = FakeDesktop("org.gnome.Nautilus", selection=["/tmp/a.txt"])

        desktop.press_alt_s()

        command = desktop.launched[0]
        self.assertTrue(command[1].endswith("omni_care.py"))
        self.assertEqual(command[2:], ["/tmp/a.txt"])

    def test_an_old_clipboard_is_never_taken_for_the_selection(self):
        desktop = FakeDesktop(
            "org.gnome.Nautilus", selection=["/tmp/a.txt"], clipboard=["/tmp/Old.txt"],
            copy_works=False,
        )

        desktop.press_alt_s()

        self.assertEqual(desktop.launched, [])


if __name__ == "__main__":
    unittest.main()
