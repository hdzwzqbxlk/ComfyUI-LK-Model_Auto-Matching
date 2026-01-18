import unittest
from unittest.mock import MagicMock
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock folder_paths BEFORE importing scanner
sys.modules['folder_paths'] = MagicMock()

from scanner import ModelScanner
from matcher import ModelMatcher

class TestModelMatcher(unittest.TestCase):
    def setUp(self):
        # Mock scanner
        self.scanner = MagicMock(spec=ModelScanner)
        self.scanner.get_all_models.return_value = [
            {"filename": "sd_xl_base_1.0.safetensors", "path": "/path/to/sd_xl_base_1.0.safetensors", "type": "checkpoints"},
            {"filename": "v1-5-pruned-emaonly.ckpt", "path": "/path/to/v1-5-pruned-emaonly.ckpt", "type": "checkpoints"},
            {"filename": "custom_folder/my_model_v1.safetensors", "path": "/path/to/custom_folder/my_model_v1.safetensors", "type": "checkpoints"},
            {"filename": "lora_v1.safetensors", "path": "/path/to/lora_v1.safetensors", "type": "loras"}
        ]
        self.matcher = ModelMatcher(self.scanner)

    def test_exact_match_simple(self):
        # Case: Filename exactly matches (normalized) but different extension
        # Input: "v1-5-pruned-emaonly.pt" -> Local: "v1-5-pruned-emaonly.ckpt"
        # Since strings are different, it won't be filtered out as "already correct"
        items = [{"id": 1, "current": "v1-5-pruned-emaonly.pt", "node_type": "CheckpointLoaderSimple", "widget_name": "ckpt_name"}]
        result = self.matcher.match(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_value"], "v1-5-pruned-emaonly.ckpt")

    def test_exact_match_different_path(self):
        # Case: Filename matches, but incoming path is different
        items = [{"id": 1, "current": "Internet/Models/v1-5-pruned-emaonly.ckpt", "node_type": "CheckpointLoaderSimple", "widget_name": "ckpt_name"}]
        result = self.matcher.match(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_value"], "v1-5-pruned-emaonly.ckpt")

    def test_fuzzy_match(self):
        # Case: Filename slightly different
        # Input: "sd_xl_base_1.0_0.9vae.safetensors"
        # Available: "sd_xl_base_1.0.safetensors"
        items = [{"id": 1, "current": "sd_xl_base_1.0_0.9vae.safetensors", "node_type": "CheckpointLoaderSimple", "widget_name": "ckpt_name"}]
        result = self.matcher.match(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_value"], "sd_xl_base_1.0.safetensors")

    def test_fuzzy_match_case_insensitive(self):
        # Case: Case mismatch
        items = [{"id": 1, "current": "SD_XL_BASE_1.0.safetensors", "node_type": "CheckpointLoaderSimple", "widget_name": "ckpt_name"}]
        result = self.matcher.match(items)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["matched_value"], "sd_xl_base_1.0.safetensors")

    def test_no_match(self):
        # Case: Completely different
        items = [{"id": 1, "current": "totally_unknown_model.ckpt", "node_type": "CheckpointLoaderSimple", "widget_name": "ckpt_name"}]
        result = self.matcher.match(items)
        self.assertEqual(len(result), 0)

if __name__ == '__main__':
    unittest.main()
