import time
import re
import sys
import os
import types

# Mock folder_paths
mock_folder_paths = types.ModuleType("folder_paths")
mock_folder_paths.folder_names_and_paths = {}
sys.modules["folder_paths"] = mock_folder_paths

sys.path.append(os.getcwd())
from core.utils import AdvancedTokenizer

text = "Wan2.1_T2V_14B_lightx2v_cfg_step_distill_lora_rank64.safetensors"

print(f"Testing Tokenizer on: {text}")

start = time.time()
for i in range(10000):
    tokens = AdvancedTokenizer.tokenize(text)
end = time.time()

print(f"10,000 runs took: {end - start:.4f} seconds")
print(f"Per call: {(end - start)/10000 * 1000:.4f} ms")
print(f"Result: {tokens}")
