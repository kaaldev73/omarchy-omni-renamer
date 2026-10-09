import tempfile
import unittest
from pathlib import Path
from unittest import mock

from omni_agent import safe_recommendations


class AgentRecommendationTests(unittest.TestCase):
    def test_local_baseline_uses_text_title_without_an_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("# Quarterly Planning Notes\nDetails", encoding="utf-8")
            with mock.patch("omni_agent.codex_recommendations", return_value=None):
                result = safe_recommendations([path], include_content=True)
            self.assertEqual(result["provider"], "local-baseline")
            self.assertEqual(
                result["recommendations"][0]["suggested_name"],
                "quarterly-planning-notes.txt",
            )

    def test_metadata_only_does_not_read_file_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Private Notes.txt"
            path.write_text("Secret Project", encoding="utf-8")
            with mock.patch("omni_agent.codex_recommendations", return_value=None):
                result = safe_recommendations([path], include_content=False)
            self.assertEqual(
                result["recommendations"][0]["suggested_name"],
                "private-notes.txt",
            )


if __name__ == "__main__":
    unittest.main()
