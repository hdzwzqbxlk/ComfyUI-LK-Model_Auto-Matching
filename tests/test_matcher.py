import unittest
from unittest.mock import MagicMock
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import ModelScanner
from matcher import ModelMatcher

class TestModelMatcher(unittest.TestCase):
    def setUp(self):
        # Mock scanner
        self.scanner = MagicMock(spec=ModelScanner)
        self.scanner.scan_all_models.return_value = {
            "checkpoints": [
                "sd_xl_base_1.0.safetensors", 
                "v1-5-pruned-emaonly.ckpt", 
                "custom_folder/my_model_v1.safetensors"
            ],
            "loras": ["lora_v1.safetensors"]
        }
        self.matcher = ModelMatcher(self.scanner)
        self.matcher.refresh_models()

    def test_exact_match_simple(self):
        # Case: Filename exactly matches one in list
        result = self.matcher.match("v1-5-pruned-emaonly.ckpt", "checkpoints")
        self.assertEqual(result, "v1-5-pruned-emaonly.ckpt")

    def test_exact_match_different_path(self):
        # Case: Filename matches, but incoming path is different
        # Input: "Internet/Models/v1-5-pruned-emaonly.ckpt"
        # Available: "v1-5-pruned-emaonly.ckpt"
        result = self.matcher.match("Internet/Models/v1-5-pruned-emaonly.ckpt", "checkpoints")
        self.assertEqual(result, "v1-5-pruned-emaonly.ckpt")

    def test_fuzzy_match(self):
        # Case: Filename slightly different
        # Input: "sd_xl_base_1.0_0.9vae.safetensors"
        # Available: "sd_xl_base_1.0.safetensors"
        # Similarity should be high enough
        result = self.matcher.match("sd_xl_base_1.0_0.9vae.safetensors", "checkpoints", threshold=0.6)
        self.assertEqual(result, "sd_xl_base_1.0.safetensors")

    def test_fuzzy_match_case_insensitive(self):
        # Case: Case mismatch
        # Input: "SD_XL_BASE_1.0.safetensors"
        result = self.matcher.match("SD_XL_BASE_1.0.safetensors", "checkpoints")
        self.assertEqual(result, "sd_xl_base_1.0.safetensors")

    def test_no_match(self):
        # Case: Completely different
        result = self.matcher.match("totally_unknown_model.ckpt", "checkpoints")
        self.assertIsNone(result)

    def test_wrong_type(self):
        # Case: Looking for lora in checkpoints
        # Input: "lora_v1.safetensors" associated with "checkpoints" type
        # Should fail unless it's in checkpoints list (it isn't)
        result = self.matcher.match("lora_v1.safetensors", "checkpoints")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
