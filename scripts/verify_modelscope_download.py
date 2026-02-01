import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock ComfyUI dependencies
from unittest.mock import MagicMock
sys.modules["folder_paths"] = MagicMock()
sys.modules["comfy"] = MagicMock()
sys.modules["comfy.utils"] = MagicMock()

from core.searcher import ModelScopeFileSearchProvider

async def verify_modelscope():
    provider = ModelScopeFileSearchProvider({})
    
    # Test Case 1: Known Model (Wan-Video)
    filename = "wan2.1_i2v.safetensors" 
    query = "Wan 2.1"
    
    print(f"Testing ModelScope Provider with query: '{query}' for file: '{filename}'")
    
    results = await provider.search(query, filename)
    
    if not results:
        print("[FAIL] No results found.")
        return
        
    print(f"[SUCCESS] Found {len(results)} results:")
    for res in results:
        print(f"  - Source: {res['source']}")
        print(f"    Name: {res['name']}")
        print(f"    URL: {res['url']}")
        print(f"    Score: {res['score']}")
        
        if "modelscope.cn/api/v1/models" in res['url'] and "Revision=master" in res['url']:
            print("    [Pass] URL format correct (Direct API Link)")
        else:
            print("    [Fail] URL format incorrect")

if __name__ == "__main__":
    asyncio.run(verify_modelscope())
