import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import AdvancedTokenizer

class TestQuantization(unittest.TestCase):
    def test_detect_quantization(self):
        self.assertEqual(AdvancedTokenizer.detect_quantization("foo_bf16.safetensors"), "bf16")
        self.assertEqual(AdvancedTokenizer.detect_quantization("foo-FP16.safetensors"), "fp16")
        self.assertEqual(AdvancedTokenizer.detect_quantization("foo.q4_k_m.gguf"), "q4_k_m")
        self.assertIsNone(AdvancedTokenizer.detect_quantization("foo.safetensors"))

    def test_precision_mismatch(self):
        # BF16 != FP16
        score = AdvancedTokenizer.calculate_similarity("model_bf16.safetensors", "model_fp16.safetensors")
        self.assertEqual(score, 0.0, "BF16 should mismatch FP16")

    def test_gguf_quant_mismatch(self):
        # Q4 != Q5
        score = AdvancedTokenizer.calculate_similarity("model-Q4_K_M.gguf", "model-Q5_0.gguf")
        self.assertEqual(score, 0.0, "GGUF Quants should mismatch")

    def test_mixed_precision_allowed(self):
        # Specific matches Ambiguous -> Allowed
        # (Assuming general model 'v1' vs 'v1_fp16' is acceptable if user didn't ask for specific v1_bf16)
        # But here valid comparison is same name different quant
        score = AdvancedTokenizer.calculate_similarity("model_v1.safetensors", "model_v1_fp16.safetensors")
        self.assertGreater(score, 0.0, "Ambiguous vs Specific should be allowed (fuzzy)")

    def test_same_precision(self):
        score = AdvancedTokenizer.calculate_similarity("model_v1_bf16.safetensors", "model_v1_bf16_pruned.safetensors")
        self.assertGreater(score, 0.8, "Same precision should match high")

if __name__ == '__main__':
    unittest.main()
