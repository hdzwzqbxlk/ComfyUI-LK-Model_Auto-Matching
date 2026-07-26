
import asyncio
import os
import sys
from pathlib import Path

# Mock environment
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Mock ComfyUI dependencies
sys.modules['folder_paths'] = type('folder_paths', (), {
    'get_filename_list': lambda x: [],
    'base_path': str(project_root),
    'models_dir': str(project_root / "models")
})
sys.modules['comfy'] = type('comfy', (), {})
sys.modules['comfy.utils'] = type('utils', (), {'ProgressBar': lambda x: None})

from core.searcher import ModelSearcher
# from core.models_db import ModelDatabase

async def run_verification():
    print("="*60)
    print("🚀  STARTING FINAL SYSTEM VERIFICATION v3.5.0")
    print("="*60)
    
    config = {
        "providers": {
            "civitai_api_key": "dummy",
            "hf_token": "dummy"
        },
        "search": {
            "use_cache": False,
            "max_results": 5
        },
        "network": {
            "timeout": 20
        }
    }
    
    searcher = ModelSearcher()
    searcher.config = config
    
    test_cases = [
        # 1. Chinese Model -> ModelScope Priority (Existing file in Wan-AI repo)
        {
            "name": "Wan 2.1 (China) Priority",
            "filename": "Wan2.1_VAE.pth", 
            "expected_source": "ModelScope",
            "min_score": 0.5
        },
        # 2. Global Model -> HuggingFace Priority
        {
            "name": "Flux.1 Dev (Global)",
            "filename": "flux1-dev-fp8.safetensors",
            "expected_source": "HuggingFace",
            "min_score": 0.6
        },
        # 3. Dynamic Discovery (Unknown Name)
        {
            "name": "Dynamic Discovery",
            "filename": "My-Awesome-LoRA-v1.safetensors",
            "expected_source": "ModelScope", # Should try, even if fail
            "optional": True # Might not find anything, but log check is key
        },
        {
            "name": "Civitai Complex Name (Wan Priority)",
            "filename": "aniWan2114BFp8E4m3fn_i2v480pNew.safetensors",
            "expected_source": "ModelScope",
            "min_score": 0.8
        }
    ]
    
    passed = 0
    total = len(test_cases)
    
    for case in test_cases:
        print(f"\n🧪  Testing: {case['name']}")
        print(f"    File: {case['filename']}")
        
        try:
            results = await searcher.search(case['filename'])
            
            if not results:
                print(f"    ❌  FAILED: No results found.")
                continue
                
            top_result = results[0]
            print(f"    🏆  Top Result: {top_result['name']}")
            print(f"        Source: {top_result['source']}")
            print(f"        URL: {top_result['url']}")
            
            # Validation
            source_check = False
            if case['expected_source'] == "Any":
                source_check = True
            elif isinstance(case['expected_source'], list):
                source_check = any(s in top_result['source'] for s in case['expected_source'])
            else:
                source_check = case['expected_source'] in top_result['source']
                
            keyword_check = True
            if "expected_keyword" in case:
                keyword_check = case['expected_keyword'].lower() in top_result['url'].lower() or \
                                case['expected_keyword'].lower() in top_result['filename'].lower()
            
            if source_check and keyword_check:
                print(f"    ✅  PASSED")
                passed += 1
            else:
                print(f"    ⚠️  WARNING: Result might not match expectation.")
                print(f"        Expected Source: {case['expected_source']}")
                print(f"        Expected Keyword: {case.get('expected_keyword', 'N/A')}")
                
        except Exception as e:
            print(f"    ❌  ERROR: {e}")
            import traceback
            traceback.print_exc()
            
    print("\n" + "="*60)
    print(f"📊  SUMMARY: {passed}/{total} Tests Passed")
    print("="*60)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_verification())
