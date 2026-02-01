"""
将抓取的模型数据转换为 Python 数据库模块 core/models_db.py
整合来源:
1. kijai_all_models.txt (Kijai/WanVideo_comfy)
2. comfy_gguf_models.json (Comfy-Org, GGUF Repos)
"""
import json
import os

OUTPUT_FILE = "core/models_db.py"

def main():
    print("Building models database...")
    
    # 1. 基础头部代码
    header = '''"""
[Auto-Generated] 全量模型精确匹配数据库
包含仓库: Kijai, Comfy-Org, City96, bartowski, mradermacher, MaziyarPanahi
总模型数: {total_count}
生成时间: {timestamp}
"""
import os

# Civitai 风格命名映射 (手动维护)
CIVITAI_MAP = {{
    # aniWan 系列
    "aniwan2114bfp8e4m3fn_i2v480pnew": "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
    "aniwan2114bfp8e4m3fn": "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
    "aniwan21t2v14b": "Wan2_1-T2V-14B_fp8_e4m3fn.safetensors",
    "aniwani2v14b": "Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
    
    # rCM LoRA
    "wan_2_1_t2v_14b_rcm_lora_average_rank_83": "LoRAs/rCM/Wan_2_1_T2V_14B_480p_rCM_lora_average_rank_83_bf16.safetensors",
    "wan_2_1_t2v_14b_rcm_lora_average_rank_148": "LoRAs/rCM/Wan_2_1_T2V_14B_480p_rCM_lora_average_rank_148_bf16.safetensors",
    "wan_2_1_t2v_14b_720p_rcm": "LoRAs/rCM/Wan_2_1_T2V_14B_720p_rCM_lora_average_rank_94_bf16.safetensors",
    
    # InfiniteTalk
    "infinitetalk_single": "InfiniteTalk/Wan2_1-InfiniTetalk-Single_fp16.safetensors",
    "infinitetalk_multi": "InfiniteTalk/Wan2_1-InfiniteTalk-Multi_fp16.safetensors",
}}

# 全量模型数据库
# Key: 小写文件名 (无路径)
# Value: {{ repo_id, path, filename }}
MODELS_DB = {{

'''

    models_data = {}
    
    # 2. 处理 Kijai 数据
    if os.path.exists("kijai_all_models.txt"):
        with open("kijai_all_models.txt", "r", encoding="utf-8") as f:
            for line in f:
                path = line.strip()
                if not path: continue
                filename = os.path.basename(path)
                key = filename.lower()
                models_data[key] = {
                    "repo_id": "Kijai/WanVideo_comfy",
                    "path": path,
                    "filename": filename,
                    "source": "Kijai"
                }
    
    # 3. 处理 Comfy-Org/GGUF 数据
    if os.path.exists("comfy_gguf_models.json"):
        with open("comfy_gguf_models.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            for repo_id, files in data.items():
                source_type = "Comfy-Org" if "Comfy-Org" in repo_id else "GGUF"
                for path in files:
                    filename = os.path.basename(path)
                    key = filename.lower()
                    # 如果重名，保留之前的 (Kijai 优先)，或者覆盖
                    if key not in models_data:
                        models_data[key] = {
                            "repo_id": repo_id,
                            "path": path,
                            "filename": filename,
                            "source": source_type
                        }

    # 4. 生成代码
    import datetime
    content = header.format(total_count=len(models_data), timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    for key, info in sorted(models_data.items()):
        content += f'    "{key}": {json.dumps(info, ensure_ascii=False)},\n'
        
    content += "}\n\n"
    
    # 5. 添加搜索函数
    content += '''
def find_best_match_in_db(filename: str) -> tuple:
    """
    在全量数据库中查找最佳匹配
    返回: (matched_info, score) 或 (None, 0)
    matched_info 是包含 repo_id, path, url 的字典
    """
    try:
        from rapidfuzz import fuzz, process
    except ImportError:
        return (None, 0)
        
    base = os.path.basename(filename)
    base_lower = base.lower()
    name_no_ext = os.path.splitext(base_lower)[0]
    
    # 1. 精确匹配 (最快)
    if base_lower in MODELS_DB:
        info = MODELS_DB[base_lower]
        return (_enrich_info(info), 1.0)
        
    # 2. Civitai 映射
    clean_name = name_no_ext.replace('-', '_').replace('.', '_')
    for map_key, map_path in CIVITAI_MAP.items():
        if map_key in clean_name:
            # 需要反查这个 path 对应的 repo 信息
            # 这里简化处理，只对 Kijai 的有效
            if "Kijai" in "Kijai": # Hack check
                return ({
                    "repo_id": "Kijai/WanVideo_comfy",
                    "path": map_path,
                    "filename": os.path.basename(map_path),
                    "url": f"https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/{map_path}",
                    "pageUrl": "https://huggingface.co/Kijai/WanVideo_comfy"
                }, 0.99)

    # 3. RapidFuzz 模糊匹配 (针对 3000+ 文件)
    # 提取所有 key 用于匹配
    all_keys = list(MODELS_DB.keys())
    
    # 使用 token_set_ratio (处理词序, 如 aniWan vs Wan_ani)
    result = process.extractOne(base_lower, all_keys, scorer=fuzz.token_set_ratio)
    if result and result[1] >= 85:
        matched_key = result[0]
        return (_enrich_info(MODELS_DB[matched_key]), result[1] / 100)
        
    # 使用 partial_ratio (处理缺失, 如缺 480p)
    # 注意: partial_ratio 可能会匹配到错误的短文件名，需要长度惩罚
    result = process.extractOne(base_lower, all_keys, scorer=fuzz.partial_ratio)
    if result and result[1] >= 90:
        matched_key = result[0]
        # 简单长度检查
        if len(matched_key) > len(base_lower) * 0.5:
            return (_enrich_info(MODELS_DB[matched_key]), result[1] / 100)

    return (None, 0)

def _enrich_info(info):
    """添加 URL 字段"""
    new_info = info.copy()
    new_info["url"] = f"https://huggingface.co/{info['repo_id']}/resolve/main/{info['path']}"
    new_info["pageUrl"] = f"https://huggingface.co/{info['repo_id']}/tree/main"
    return new_info
'''

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Database generated with {len(models_data)} entries at {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
