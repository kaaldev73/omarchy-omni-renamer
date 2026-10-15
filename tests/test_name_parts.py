import unittest

from name_parts import Choices, propose_name


class ProposeNameTests(unittest.TestCase):
    def test_style_shapes_the_name(self):
        self.assertEqual(propose_name("My Report.txt", Choices("kebab-case")), "my-report.txt")

    def test_name_parts_go_in_order_date_name_version_initials(self):
        choices = Choices("kebab-case", date="20261015", version="2", initials="KR")
        self.assertEqual(propose_name("My Report.txt", choices), "20261015-my-report-v2-KR.txt")

    def test_snake_case_separates_name_parts_with_underscores(self):
        choices = Choices("snake_case", date="2026", version="2", initials="KR")
        self.assertEqual(propose_name("My Report.txt", choices), "2026_my_report_v2_KR.txt")

    def test_existing_name_parts_survive_the_style_when_left_alone(self):
        self.assertEqual(
            propose_name("20261001 Report v1 KR.pdf", Choices("kebab-case")),
            "20261001-report-v1-KR.pdf",
        )

    def test_chosen_name_parts_replace_existing_ones(self):
        choices = Choices("kebab-case", date="20261015", version="2", initials="AB")
        self.assertEqual(
            propose_name("20261001-report-v1-KR.pdf", choices), "20261015-report-v2-AB.pdf"
        )

    def test_an_empty_version_bumps_the_existing_one(self):
        self.assertEqual(propose_name("report-v1.pdf", Choices(version="")), "report-v2.pdf")

    def test_an_empty_version_starts_at_v1(self):
        self.assertEqual(propose_name("report.pdf", Choices(version="")), "report-v1.pdf")

    def test_a_version_split_by_the_old_care_app_is_repaired(self):
        self.assertEqual(propose_name("sales-report-v-1.docx", Choices()), "sales-report-v1.docx")

    def test_a_date_counts_only_at_the_start(self):
        self.assertEqual(
            propose_name("final-report-2023.pdf", Choices(date="20261015")),
            "20261015-final-report-2023.pdf",
        )

    def test_a_typed_v_is_not_doubled(self):
        self.assertEqual(propose_name("report.pdf", Choices(version="v3")), "report-v3.pdf")

    def test_a_version_split_by_snake_case_is_repaired(self):
        self.assertEqual(propose_name("sales_report_v_1.docx", Choices(version="")), "sales-report-v2.docx")

    def test_a_hidden_item_stays_hidden(self):
        self.assertEqual(propose_name(".bashrc", Choices(version="2")), ".bashrc-v2")

    def test_a_tar_archive_keeps_its_whole_extension(self):
        self.assertEqual(propose_name("Report.tar.gz", Choices(version="2")), "report-v2.tar.gz")


if __name__ == "__main__":
    unittest.main()
