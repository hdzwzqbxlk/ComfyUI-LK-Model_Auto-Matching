import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import AdvancedTokenizer

class TestModelSemantics(unittest.TestCase):
    
    def test_base_model_detection(self):
        """Verify detection of Base Model Architecture"""
        # SDXL
        self.assertEqual(AdvancedTokenizer.detect_base_model("Juggernaut_XL_v9.safetensors"), "sdxl")
        self.assertEqual(AdvancedTokenizer.detect_base_model("sd_xl_base_1.0.safetensors"), "sdxl")
        
        # SD1.5
        self.assertEqual(AdvancedTokenizer.detect_base_model("v1-5-pruned.ckpt"), "sd15")
        # self.assertEqual(AdvancedTokenizer.detect_base_model("anything-v3.0.safetensors"), "sd15") # ambiguous, let it be unknown logic handle it
        
        # Flux
        self.assertEqual(AdvancedTokenizer.detect_base_model("flux1-dev.safetensors"), "flux")
        self.assertEqual(AdvancedTokenizer.detect_base_model("flux_schnell_fp8.sft"), "flux")
        
        # Pony (Special case, usually SDXL based but treated as distinct ecosystem)
        self.assertEqual(AdvancedTokenizer.detect_base_model("Pony_Diffusion_V6_XL.safetensors"), "pony")
        
        # Qwen
        self.assertEqual(AdvancedTokenizer.detect_base_model("qwen_image_edit_2511.safetensors"), "qwen")

    def test_model_type_compatibility(self):
        """Test strict compatibility rules"""
        # SDXL != SD1.5
        score = AdvancedTokenizer.calculate_similarity("Juggernaut_XL.safetensors", "Juggernaut_v7_SD15.safetensors")
        self.assertEqual(score, 0.0, "SDXL should not match SD1.5")
        
        # Inpainting != Base (Detected by Critical Terms mostly now, but checked via similarity)
        score = AdvancedTokenizer.calculate_similarity("model_inpainting.safetensors", "model_base.safetensors")
        self.assertEqual(score, 0.0, "Inpainting should not match Base")
        
        # LCM matches Base (Compatible) - Open for debate, usually we allow variants
        # But user wants strictness. Let's say LCM is a Variant, so it should be allowed but scored lower?
        # NO, user said "Don't be lazy". Inpainting is hard incompatible. LCM is architecture change.
        # But LCM LoRA can be applied to Base. LCM Checkpoint is standalone.
        # Let's assume Inpainting is Hard Incompatible.
