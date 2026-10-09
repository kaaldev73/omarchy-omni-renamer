import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class ManifestTests(unittest.TestCase):
    def test_plugin_is_a_service_stub_with_an_existing_entry_point(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["kinds"], ["service"])
        self.assertEqual(list(manifest["entryPoints"]), ["service"])
        self.assertTrue((ROOT / manifest["entryPoints"]["service"]).is_file())


if __name__ == "__main__":
    unittest.main()
