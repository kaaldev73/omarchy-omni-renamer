import unittest
from unittest import mock

import omni_dispatch


class ShortcutTests(unittest.TestCase):
    def test_alt_s_outside_the_file_manager_is_forwarded_unchanged(self):
        with (
            mock.patch.object(omni_dispatch, "active_class", return_value="kitty"),
            mock.patch.object(omni_dispatch.subprocess, "Popen") as popen,
        ):
            omni_dispatch.main()

        popen.assert_called_once_with(["wtype", "-M", "alt", "s", "-m", "alt"])

    def test_alt_s_in_the_file_manager_opens_the_window_on_the_selection(self):
        with (
            mock.patch.object(omni_dispatch, "active_class", return_value="org.gnome.nautilus"),
            mock.patch.object(omni_dispatch, "selected_paths", return_value=["/tmp/a.txt"]),
            mock.patch.object(omni_dispatch.subprocess, "Popen") as popen,
        ):
            omni_dispatch.main()

        command = popen.call_args.args[0]
        self.assertTrue(command[1].endswith("omni_care.py"))
        self.assertEqual(command[2:], ["/tmp/a.txt"])


if __name__ == "__main__":
    unittest.main()
