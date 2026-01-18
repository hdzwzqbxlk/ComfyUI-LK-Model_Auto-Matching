"""
网络搜索模块测试脚本
用于验证 searcher.py 的搜索词提取和相似度计算功能
"""
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from searcher import ModelSearcher

def test_extract_search_terms():
    """测试搜索词提取功能"""
    searcher = ModelSearcher()
    
    test_cases = [
        # (输入文件名, 预期包含的关键词)
        ("realvisxl_v3.0_turbo_fp16.safetensors", ["realvisxl"]),
        ("sd_xl_base_1.0.safetensors", ["sd", "xl"]),
        ("v1-5-pruned-emaonly.ckpt", ["v1"]),
        ("flux1-dev.safetensors", ["flux1", "dev"]),
        ("SDXL_Juggernaut_XL_v9.safetensors", ["juggernaut", "xl"]),
        ("controlnet-canny-sdxl-1.0.safetensors", ["controlnet", "canny", "sdxl"]),
    ]
    
    print("=" * 60)
    print("测试: _extract_search_terms")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for filename, expected_keywords in test_cases:
        terms = searcher._extract_search_terms(filename)
        # 检查至少有一个搜索词包含预期关键词
        all_terms_text = ' '.join(terms).lower()
        
        missing = [kw for kw in expected_keywords if kw.lower() not in all_terms_text]
        
        if not missing:
            print(f"✓ {filename}")
            print(f"  -> 提取词: {terms}")
            passed += 1
        else:
            print(f"✗ {filename}")
            print(f"  -> 提取词: {terms}")
            print(f"  -> 缺失关键词: {missing}")
            failed += 1
    
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_calculate_similarity():
    """测试相似度计算功能"""
    searcher = ModelSearcher()
    
    test_cases = [
        # (名称A, 名称B, 预期相似度范围)
        ("realvisxl_v3", "realvisxl-v3.0-turbo", (0.4, 1.0)),  # 应该高
        ("sd_xl_base", "stable-diffusion-xl-base-1.0", (0.3, 1.0)),  # 中等
        ("flux1-dev", "flux.1-dev", (0.5, 1.0)),  # 应该高
        ("my_random_model", "completely_different_thing", (0.0, 0.3)),  # 应该低
        ("controlnet-canny", "controlnet_canny_sdxl", (0.4, 1.0)),  # 应该高
    ]
    
    print("\n" + "=" * 60)
    print("测试: _calculate_similarity")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name_a, name_b, (min_score, max_score) in test_cases:
        score = searcher._calculate_similarity(name_a, name_b)
        
        if min_score <= score <= max_score:
            print(f"✓ '{name_a}' vs '{name_b}'")
            print(f"  -> 相似度: {score:.3f} (预期范围: {min_score}-{max_score})")
            passed += 1
        else:
            print(f"✗ '{name_a}' vs '{name_b}'")
            print(f"  -> 相似度: {score:.3f} (预期范围: {min_score}-{max_score}) - 超出范围!")
            failed += 1
    
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return failed == 0


def test_noise_removal():
    """测试噪声词移除"""
    searcher = ModelSearcher()
    
    print("\n" + "=" * 60)
    print("测试: 噪声后缀词移除")
    print("=" * 60)
    
    # 包含大量噪声词的文件名
    noisy_filename = "realvisxl_v3_turbo_fp16_pruned_emaonly_final.safetensors"
    terms = searcher._extract_search_terms(noisy_filename)
    
    # 所有提取的词中不应包含这些噪声词
    noise_words = {'fp16', 'pruned', 'emaonly', 'final', 'safetensors'}
    all_terms_text = ' '.join(terms).lower()
    
    found_noise = [w for w in noise_words if w in all_terms_text]
    
    if not found_noise:
        print(f"✓ 噪声词已正确移除")
        print(f"  输入: {noisy_filename}")
        print(f"  输出: {terms}")
        return True
    else:
        print(f"✗ 仍包含噪声词: {found_noise}")
        print(f"  输入: {noisy_filename}")
        print(f"  输出: {terms}")
        return False


if __name__ == "__main__":
    print("\n🧪 ComfyUI-LK-Model_Auto-Matching 搜索模块测试\n")
    
    results = []
    results.append(("搜索词提取", test_extract_search_terms()))
    results.append(("相似度计算", test_calculate_similarity()))
    results.append(("噪声词移除", test_noise_removal()))
    
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + ("🎉 所有测试通过!" if all_passed else "⚠️ 存在失败的测试"))
