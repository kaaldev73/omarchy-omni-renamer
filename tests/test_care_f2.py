import unittest
from unittest import mock

import care_f2


class F2AdapterTests(unittest.TestCase):
    def test_f2_outside_the_file_manager_is_forwarded_unchanged(self):
        with (
            mock.patch.object(care_f2, "active_class", return_value="kitty"),
            mock.patch.object(care_f2.subprocess, "Popen") as popen,
        ):
            care_f2.main()

        popen.assert_called_once_with(["wtype", "-k", "F2"])

    def test_f2_in_the_file_manager_opens_care_with_the_selection(self):
        with (
            mock.patch.object(care_f2, "active_class", return_value="org.gnome.nautilus"),
            mock.patch.object(care_f2, "selected_paths", return_value=["/tmp/a.txt"]),
            mock.patch.object(care_f2.subprocess, "Popen") as popen,
        ):
            care_f2.main()

        command = popen.call_args.args[0]
        self.assertTrue(command[1].endswith("omni_care.py"))
        self.assertEqual(command[2:], ["/tmp/a.txt"])


if __name__ == "__main__":
    unittest.main()
