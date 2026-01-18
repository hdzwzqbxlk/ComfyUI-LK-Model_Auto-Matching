import unittest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matcher import ModelMatcher
from utils import AdvancedTokenizer

class TestStrictFormat(unittest.TestCase):
    def test_gguf_vs_safetensors(self):
        """
        Verify that Safetensors NEVER matches GGUF, even if names are very similar.
        Target: qwen_image_edit_2511_bf16.safetensors
        Candidate: qwen-image-edit-2511-Q4_K_S.gguf
        """
        scanner = MagicMock()
        scanner.get_all_models.return_value = [
            # Only the GGUF version exists locally
            {
                "filename": "QwenImageEdit\\qwen-image-edit-2511-Q4_K_S.gguf", 
                "path": "D:\\models\\gguf", 
                "type": "checkpoints"
            }
        ]
        
        matcher = ModelMatcher(scanner)
        # Force build
        matcher._build_index()
        
        # Request
        items = [{
            "id": 1, 
            "current": "qwen_image_edit_2511_bf16.safetensors", 
            "node_type": "CheckpointLoader", 
            "widget_name": "ckpt"
        }]
        
        result = matcher.match(items)
        
        # Expectation: NO MATCH because format differs
        print(f"\n[Test Strict] Input: {items[0]['current']}")
        if result:
            print(f"Matched: {result[0]['matched_value']}")
        else:
            print("Matched: None")
            
        self.assertEqual(len(result), 0, "Should NOT match GGUF to Safetensors")

    def test_safetensors_variant(self):
        """
        Verify that Safetensors CAN match other Safetensors if closely related.
        Target: qwen_image_edit_2511_bf16.safetensors
        Candidate: qwen_image_edit_2511_fp16.safetensors
        """
        scanner = MagicMock()
        scanner.get_all_models.return_value = [
            {
                "filename": "qwen_image_edit_2511_fp16.safetensors", 
                "path": "D:\\models\\fp16", 
                "type": "checkpoints"
            }
        ]
        
        matcher = ModelMatcher(scanner)
        matcher._build_index()
        
        items = [{
            "id": 1, 
            "current": "qwen_image_edit_2511_bf16.safetensors", 
            "node_type": "CheckpointLoader", 
            "widget_name": "ckpt"
        }]
        
        result = matcher.match(items)
        
        # Expectation: MATCH (Variant)
        print(f"\n[Test Variant] Input: {items[0]['current']}")
        if result:
            print(f"Matched: {result[0]['matched_value']}")
        else:
            print("Matched: None")

        self.assertEqual(len(result), 1, "Should match variant of same format")
        self.assertEqual(result[0]['matched_value'], "qwen_image_edit_2511_fp16.safetensors")

if __name__ == '__main__':
    unittest.main()
