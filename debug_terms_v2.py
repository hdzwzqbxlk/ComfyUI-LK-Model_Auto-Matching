import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import AdvancedTokenizer

term = "qwen_image_edit_2511_Q4_K_S.gguf"
terms = AdvancedTokenizer.extract_search_terms(term)
print(f"Terms: {terms}")

# Expectation: "qwen image edit 2511 Q4 K S" should be the FIRST or high priority term.
