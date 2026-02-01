import re
import os

# 尝试导入 rapidfuzz (高性能模糊匹配库)
from rapidfuzz import fuzz as rf_fuzz
from rapidfuzz import process as rf_process
USE_RAPIDFUZZ = True

# 噪声后缀词（仅过滤纯技术后缀，不过滤版本号和模型组件名）
import json

# ============================================================
# 数据加载逻辑 (Phase 1: JSON-driven)
# ============================================================

def load_models_data():
    """从 models_data.json 加载配置，如果失败则返回默认值"""
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'models_data.json')
    data = {}
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"[ModelMatcher] Error loading models_data.json: {e}")
    
    return data

_DATA = load_models_data()

# 1. 噪声后缀词
NOISE_SUFFIXES = set(_DATA.get('noise_suffixes', {
    'fp16', 'fp32', 'bf16', 'fp8', 'int8', 'int4', 'q4', 'q8', 'gguf', 'f16', 'f32',
    'pruned', 'ema', 'emaonly', 'noembed', 'noema',
    'safetensors', 'ckpt', 'pt', 'bin', 'pth', 'onnx', 'pkl',
    'fix', 'fixed', 'final', 'official', 'release',
    'sfw', 'nsfw',
    'lightning', '8steps', '4steps', '2steps', 'turbo', 'lcm', 'hyper',
}))

# 2. 核心模型词保护列表
PROTECTED_TERMS = set(_DATA.get('protected_terms', {
    'sd', 'sd15', 'sd21', 'sd3', 'sdxl', 'stable', 'diffusion',
    'base', 'refiner',
    'flux', 'flux1', 'schnell', 'dev',
    'vae', 'unet', 'lora', 'controlnet', 'clip', 'embeddings',
    'qwen', 'llama', 'mistral', 'realvis', 'juggernaut',
    'inpainting',
}))

# 3. 常见模型族识别模式
MODEL_PATTERNS = _DATA.get('model_patterns', {
    r'v1[\-_\.]?5': 'stable diffusion 1.5',
    r'v2[\-_\.]?1': 'stable diffusion 2.1',
    r'sd[\-_]?xl': 'stable diffusion xl',
    r'sd[\-_]?3': 'stable diffusion 3',
    r'flux[\-_\.]?1': 'flux.1',
})

# 4. 常见模型名缩写映射
MODEL_ALIASES = _DATA.get('model_aliases', {
    'sdxl': 'stable diffusion xl',
    'sd15': 'stable diffusion 1.5',
    'sd21': 'stable diffusion 2.1',
    'sd': 'stable diffusion',
    'flux': 'flux',
    'realvis': 'realvisxl',
    'jugg': 'juggernaut',
    'qwen': 'qwen',
})

# 5. ComfyUI 官方主流模型精确映射表
# [v3.3.1] 基于用户模型库样本扩充
COMFYUI_POPULAR_MODELS = _DATA.get('popular_models', {
    # 基础模型
    'v1-5-pruned-emaonly': 'Comfy-Org/stable-diffusion-v1-5-archive',
    'sd_xl_base_1.0': 'stabilityai/stable-diffusion-xl-base-1.0',
    'flux1-dev': 'black-forest-labs/FLUX.1-dev',
    'flux1-dev-fp8': 'black-forest-labs/FLUX.1-dev',
    'flux1-schnell': 'black-forest-labs/FLUX.1-schnell',
    
    # Wan 系列
    'infinitetalk': 'InfiniteTalk/Wan2_1-InfiniTetalk-Single',
    'wan2_1-infinitetalk': 'InfiniteTalk/Wan2_1-InfiniTetalk-Single',
    'wan2.1-i2v-14b': 'Wan-AI/Wan2.1-I2V-14B-480P',
    'wan2.1-t2v-14b': 'Wan-AI/Wan2.1-T2V-14B',
    'wan2.2-remix': 'FX-FeiHou/Wan2.2-Remix',
    
    # Qwen 系列
    'qwen_image': 'Qwen/Qwen2.5-Coder-32B-Instruct',
    'qwen_image_edit_2509': 'Kijai/Qwen-Image-Edit-2509',
    'qwen_image_edit_2511': 'Kijai/Qwen-Image-Edit-2511',
    
    # Z-Image 系列
    'z_image': 'Zongjian/Z-Image',
    'z_image_turbo': 'Zongjian/Z-Image-Turbo',
    
    # LTX 系列
    'ltx-2-19b': 'Lightricks/LTX-Video-2-19B',
})

# 6. 变体后缀
VARIANT_SUFFIXES = set(_DATA.get('variant_suffixes', {
    'q4', 'q5', 'q8', 'bf16', 'fp16', 'fp8', 'gguf', 'safetensors',
    'pruned', 'ema', 'lightning', 'turbo',
    'inpainting', 'depth', 'canny',
}))

# 7. 核心功能词保护列表
CRITICAL_TERMS = set(_DATA.get('critical_terms', {
    'vae', 'lora', 'upscale', 'refiner', 'inpainting',
    'lightning', 'turbo', 'lcm', 'hyper',
    'depth', 'canny', 'openpose',
}))

class AdvancedTokenizer:
    """
    统一的智能分词器，用于本地匹配和网络搜索
    """
    


    @staticmethod
    def _normalize_text(text):
        """
        统一的文本预处理/归一化逻辑
        """
        text = text.lower()
        
        # 1. CJK Segmentation
        text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', text)
        
        # 2. Global Normalization (F.1 -> Flux 1)
        text = text.replace("f.1", "flux 1")
        text = text.replace("f 1", "flux 1")
        text = re.sub(r'\bf[\.\-_\s]?1\b', 'flux 1', text)
        
        # 3. Replace delimiters
        for char in ['_', '-', '.', ' ', '/', '\\', '[', ']', '(', ')']:
            text = text.replace(char, ' ')
            
        return text

    @staticmethod
    def tokenize(text):
        """
        将文本拆分为 token 集合 (v2.0: 语义锚点优先)
        """
        text = text.lower()
        
        # [v2.0] Pre-process: Replace delimiters that act as word boundaries (but keep dots for version numbers)
        # 将 _ 和 - 替换为空格，以便正则 \b 生效
        text_for_regex = re.sub(r'[_\-]', ' ', text)
        
        tokens = []
        
        # [v2.0] 语义保留正则 (Semantic Preservation Regex)
        # 强制保留: Wan2.1, SDXL, Pony, v1.5, 2.1, Flux.1, SD1.5
        preserve_pattern = r"(?i)\b(v\d+(\.\d+)?|sdxl|pony|wan\d*(\.\d+)?|flux[\.\-]1|sd\d+(\.\d+)?)\b"
        
        # 1. 提取保留词 (Preserved Semantic Tokens)
        # 注意：这里使用 text_for_regex 进行匹配，但在原始 text 中进行替换/删除
        preserved_matches = re.finditer(preserve_pattern, text_for_regex)
        
        # 我们需要一个掩码或替换列表来避免在 normalize 时再次处理这些词
        # 简单策略：将匹配到的词存入 tokens，并将 text 中的对应部分替换为空格
        # 但要注意 text_for_regex 和 text 的索引可能不对齐 (如果只是替换字符长度不变则没问题)
        # _ 和 - 替换为空格，长度不变。
        
        for match in preserved_matches:
            token = match.group(0).lower() # 已经是 lower
            tokens.append(token)
            # 在原始 text 中移除 (替换为空格)
            # 由于 text_for_regex 只是替换了分隔符，内容是一样的，我们可以用 token 去 replace text
            # 但要注意防止部分匹配替换 (e.g. wan2.1 vs wan2.10)
            # 这里的 replace 比较粗暴，但对于文件名通常足够
            text = text.replace(token, " ")
            
        # 2. 补救措施：Wan 系列添加 'wan'
        if "wan" in text_for_regex: 
             has_wan_prefix = any(t.startswith("wan") for t in tokens)
             if has_wan_prefix and "wan" not in tokens:
                 tokens.append("wan")

        # 3. 统一预处理 (移除点、特殊符号等)
        text = AdvancedTokenizer._normalize_text(text)

        for part in text.split():
            # 4. Alias Expansion (on individual parts)
            if part in MODEL_ALIASES:
                # e.g. "sdxl" -> "stable", "diffusion", "xl"
                expanded = MODEL_ALIASES[part].split()
                tokens.extend(expanded)
                continue

            # 5. Split alpha and numeric, BUT keep CJK characters
            # Modified regex to include non-ASCII characters (e.g. Chinese)
            # [a-z]+ matches English words
            # \d+ matches numbers
            # [^\x00-\x7f]+ matches non-ASCII (Chinese, etc.)
            sub_tokens = re.findall(r'[a-z]+|\d+|[^\x00-\x7f]+', part)
            if sub_tokens:
                tokens.extend(sub_tokens)
            else:
                tokens.append(part)
                
        # 6. Post-process tokens (Deduplicate & Clean)
        ordered_tokens = []
        seen = set()
        for t in tokens:
            s = t.strip()
            if s and s not in seen:
                seen.add(s)
                ordered_tokens.append(s)
        return ordered_tokens

    @staticmethod
    def lookup_popular_model(filename):
        """
        查找 ComfyUI 主流模型 (Phase 2: DB First, Fallback to Dict)
        返回: (repo_id, matched_key) 或 (None, None)
        """
        # 1. 尝试查询数据库 (Phase 2 Upgrade)
        try:
            from .database import db
            result = db.search_by_filename(filename)
            if result:
                name, _, _, description = result
                # 从 description 解析 repo_id ("Repo: user/repo")
                if description and "Repo: " in description:
                    repo_id = description.split("Repo: ")[1].strip()
                    return (repo_id, name)
        except ImportError:
            pass # 可能在独立脚本中运行，无法导入
        except Exception as e:
            print(f"[ModelMatcher] DB Lookup Error: {e}")

        # 2. 回退到旧的字典匹配 (用于兼容性或 DB 未覆盖的情况)
        
        # 提取基础名（无扩展名，无路径）
        base_name = os.path.basename(filename)
        # 移除常见扩展名
        for ext in ['.safetensors', '.gguf', '.ckpt', '.pt', '.bin', '.pth']:
            if base_name.lower().endswith(ext):
                base_name = base_name[:-len(ext)]
                break
        
        # 精确匹配（大小写不敏感）
        base_lower = base_name.lower()
        for key, repo_id in COMFYUI_POPULAR_MODELS.items():
            if base_lower == key.lower():
                return (repo_id, key)
        
        # 模糊匹配：尝试移除精度后缀再匹配
        # 例如 "flux1-dev-fp8" -> "flux1-dev"
        precision_suffixes = ['-fp8', '-fp16', '-bf16', '_fp8', '_fp16', '_bf16']
        for suffix in precision_suffixes:
            if base_lower.endswith(suffix):
                stripped = base_lower[:-len(suffix)]
                for key, repo_id in COMFYUI_POPULAR_MODELS.items():
                    if stripped == key.lower():
                        return (repo_id, key)
        
        return (None, None)

    @staticmethod
    def _strip_variant_terms(text):
        """
        使用 Regex 移除文件名中的技术/变体术语
        返回清洗后的字符串 (保留原有的非技术分隔符)
        
        保护关键词：dev, schnell, base, refiner, instruct 等
        移除：量化标记(Q4_K_M, bf16等)、格式后缀(gguf, safetensors等)、速度变体(lightning等)
        """
        text = text.lower()
        
        # 只移除真正的模型文件扩展名
        valid_extensions = {'.gguf', '.safetensors', '.ckpt', '.pt', '.bin', '.pth', '.onnx', '.pkl'}
        base, ext = os.path.splitext(text)
        if ext not in valid_extensions:
            # 不是有效的模型扩展名，保留原始文本
            base = text
        
        # 需要移除的技术术语集合
        remove_terms = {
            # 量化标记
            'q4', 'q5', 'q6', 'q8', 'q3', 'bf16', 'fp16', 'fp32', 'fp8', 'int8', 'int4',
            'q4_0', 'q4_1', 'q5_0', 'q5_1', 'q8_0', 'q4_k', 'q4_k_m', 'q4_k_s', 'q5_k_m', 'q5_k_s', 'q6_k',
            # 单字母量化后缀（量化标记残留，如 Q4_K_S 分解后的 k、s）
            'k', 'm', 's', 'l',
            # 格式后缀
            'gguf', 'safetensors', 'ckpt', 'pt', 'bin', 'pth', 'onnx', 'pkl',
            # GGUF 特殊精度
            'f16', 'f32',
            # 训练变体
            'pruned', 'ema', 'emaonly', 'noema', 'noembed', 'full',
            # 发布标记
            'fix', 'fixed', 'final', 'official', 'release',
            # 内容分级
            'sfw', 'nsfw',
            # 速度变体
            'lightning', 'turbo', 'hyper', 'lcm', 'simpo', '8steps', '4steps', '2steps',
        }
        
        # 保护的关键词（不管在哪里都保留）
        protected = PROTECTED_TERMS | {
            # 扩展保护词（确保这些永不被移除）
            'dev', 'schnell', 'base', 'refiner', 'instruct', 'chat', 'vl', 'vision',
            '1', '2', '3', '5', '7', '8', '13', '70',  # 常见模型版本号
        }
        
        # 分词
        parts = re.split(r'[\-_.]+', base)
        filtered = []
        
        i = 0
        while i < len(parts):
            part = parts[i]
            
            # 跳过空串
            if not part:
                i += 1
                continue
            
            # 检查是否是保护词
            if part in protected:
                filtered.append(part)
                i += 1
                continue
            
            # 检查是否是需要移除的技术术语
            if part in remove_terms:
                i += 1
                continue
            
            # 检查是否是复杂量化标记 (q/iq/sq + 数字 + 可选后缀)
            # 例如 q4, q4_k, iq2_xxs, sq1 等复杂模式
            if re.match(r'^(?:q|iq|sq|tq)\d+[a-z0-9_]*$', part):
                i += 1
                continue
            
            # 检查是否是精度标记 (f16, fp16, bf16, etc.)
            if re.match(r'^(?:bf|fp|f|int)\d+$', part):
                i += 1
                continue
            
            # 保留其他词
            filtered.append(part)
            i += 1
        
        # 重新组合
        cleaned = ' '.join(filtered)
        # 清理多余空格
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    @staticmethod
    def get_core_tokens(text):
        """
        提取核心 Token 集合
        """
        cleaned = AdvancedTokenizer._strip_variant_terms(text)
        # tokenize 返回列表，get_core_tokens 通常期望返回集合用于比较，但列表也可
        # 为了兼容 set 接口，这里转为 set
        return set(AdvancedTokenizer.tokenize(cleaned))

    @staticmethod
    def get_model_format(filename):
        """
        判断模型文件格式分类，用于防止跨格式错误匹配 (如 GGUF vs Safetensors)
        返回: 'gguf', 'checkpoint', 'lora', 'other'
        *(Lora 判定比较难仅凭后缀，主要为了区分 GGUF 和常规大模型)*
        """
        lower = filename.lower()
        if lower.endswith(".gguf"):
            return "gguf"
        elif lower.endswith((".safetensors", ".ckpt", ".pt", ".bin", ".pth")):
            return "checkpoint"
        return "other"

    @staticmethod
    def extract_search_terms(filename):
        """
        从文件名中提取多个候选搜索词（智能提取算法 - 优化版 v2）
        
        关键改进：
        1. GGUF 文件优先生成 "模型名-GGUF" 格式的搜索词
        2. 保留中文字符
        3. 保留原始连字符格式
        """
        search_terms = []
        name_only = os.path.basename(filename)
        base_name, ext = os.path.splitext(name_only)
        ext_lower = ext.lower()
        normalized_name = base_name.lower()
        
        # [v3.3.1] 预处理：清理复杂文件名
        # 1. Unicode 标点归一化 (中文标点、奇怪的引号等)
        base_name = re.sub(r'[——–—''""\'\"。，、；：！？]', '_', base_name)
        base_name = re.sub(r'[^\w\s\-_\.]', '', base_name)  # 移除其他特殊字符
        
        # 2. 去除重复词 (如 "loraWan_lora" -> "lora Wan")
        parts = re.split(r'[-_.\s]+', base_name)
        seen = set()
        unique_parts = []
        for p in parts:
            p_lower = p.lower()
            if p_lower not in seen and len(p) >= 2:
                seen.add(p_lower)
                unique_parts.append(p)
        base_name = '_'.join(unique_parts)
        
        # 3. 噪声词过滤
        noise_words = {'average', 'rank', 'ranrank', 'merged', 'merged', 'combined'}
        unique_parts = [p for p in unique_parts if p.lower() not in noise_words]
        
        normalized_name = base_name.lower()
        
        # === Phase 0: 原始文件名优先 (Direct Search Optimization) ===
        # 用户反馈表明这对 Google 搜索最有效
        # 保留原始标点符号 (. - _)
        raw_stem = '_'.join(unique_parts) if unique_parts else base_name.strip()
        
        # GGUF 特殊补全：如果文件名是 GGUF 但不含 gguf 关键字，加上它
        if ext_lower == '.gguf' and 'gguf' not in raw_stem.lower():
             raw_search = f"{raw_stem} gguf"
        else:
             raw_search = raw_stem
             
        search_terms.append(raw_search)

        # === 特殊处理：GGUF 文件 ===
        # GGUF 仓库命名规则：通常是 "模型名-GGUF"，如 "Qwen-Image-Edit-2511-GGUF"
        if ext_lower == '.gguf':
            # 移除量化标记 (Q4_K_S, Q8_0 等) 但保留模型核心名
            # 量化标记通常在最后，格式为 -Q{数字}_{字母}_{字母} 或 -Q{数字}_{数字}
            core_name = re.sub(r'[-_]Q\d+[_A-Z0-9]*$', '', base_name, flags=re.IGNORECASE)
            
            # 首选搜索词：模型名-GGUF
            gguf_search = f"{core_name}-GGUF"
            search_terms.append(gguf_search)
            
            # 备选：原始模型名 + gguf
            if 'gguf' not in core_name.lower():
                search_terms.append(f"{core_name} gguf")
            else:
                search_terms.append(core_name)
            
            # 降级：使用连字符分隔的核心词 + gguf
            core_tokens = [t for t in re.split(r'[-_]', core_name) if t]
            if core_tokens:
                tokenized_name = ' '.join(core_tokens)
                if 'gguf' not in tokenized_name.lower():
                     tokenized_name += " gguf"
                search_terms.append(tokenized_name)
        
        # === 通用处理 ===
        # Phase 1: 保留原始格式（包含中文）的清洗版本
        # 只移除量化标记，保留连字符和中文
        cleaned_base = AdvancedTokenizer._strip_variant_terms(name_only)
        
        if cleaned_base and cleaned_base not in [t.lower() for t in search_terms]:
            # 保留原始连字符格式
            clean_hyphen = re.sub(r'\s+', '-', cleaned_base.strip())
            if ext_lower == '.gguf': clean_hyphen += " gguf"
            search_terms.append(clean_hyphen)
            
            # 原始格式（保留中文）
            if ext_lower == '.gguf': cleaned_base += " gguf"
            search_terms.append(cleaned_base)
        
        # Phase 2: 中文+英文混合处理 (Chinese Core Extraction - 优化版 v4)
        # 核心改进：对于包含中文的模型名，首选完整模型名（只去扩展名和量化标记）
        # 英文核心作为备选，用于国际平台的兜底搜索
        if re.search(r'[\u4e00-\u9fff]', base_name):
            # === 2a: 完整中文名优先 (Full Name First - 用于 Liblib/ModelScope) ===
            # 保留完整模型名（包含中文），只移除量化标记
            full_name = base_name
            # 移除尾部量化标记 (如 _Q4_K_M, -Q8_0)
            full_name = re.sub(r'[-_]Q\d+[_A-Z0-9]*$', '', full_name, flags=re.IGNORECASE)
            full_name = full_name.strip()
            
            # GGUF 强制追加标识
            if ext_lower == '.gguf' and 'gguf' not in full_name.lower():
                full_name_search = f"{full_name} gguf"
            else:
                full_name_search = full_name
            
            # 将完整中文名放在最前面 (优先级最高)
            if full_name_search and full_name_search.lower() not in [t.lower() for t in search_terms]:
                search_terms.insert(0, full_name_search)
            
            # === 2b: 英文核心提取 (English Core - 用于 Civitai/HuggingFace 兜底) ===
            # 提取所有英文+数字词作为备选搜索词
            english_tokens = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', base_name)
            # 过滤掉太短的词和噪声词
            english_tokens = [t for t in english_tokens if len(t) > 1 and t.lower() not in NOISE_SUFFIXES]
            
            if english_tokens:
                # 构建英文核心搜索词
                english_core = ' '.join(english_tokens)
                # 符号归一化: F.1 -> Flux.1, F1 -> Flux 1
                english_core = re.sub(r'(?i)F[\.\\s_-]?1(?![a-z0-9])', 'Flux.1', english_core)
                
                if ext_lower == '.gguf' and 'gguf' not in english_core.lower():
                    english_core += " gguf"
                
                # 英文核心作为备选 (追加到后面，不插入最前)
                if english_core.lower() not in [t.lower() for t in search_terms]:
                    search_terms.append(english_core)

        # === Phase 2b: Deep Tokenization (CamelCase & AlphaNumeric Split) ===
        # 针对 wan22RemixSFW 这种连写情况，强制拆分为 "wan 22 Remix SFW"
        # 1. 拆分驼峰: "RemixSFW" -> "Remix SFW"
        deep_clean = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw_stem)
        # 2. 拆分数字与字母: "wan22" -> "wan 22"
        deep_clean = re.sub(r'(?<=[a-zA-Z])(?=[0-9])|(?<=[0-9])(?=[a-zA-Z])', ' ', deep_clean)
        # 3. 替换分隔符
        deep_clean = re.sub(r'[-_.]+', ' ', deep_clean)
        
        deep_clean = deep_clean.strip()
        if deep_clean and len(deep_clean) > 3 and deep_clean.lower() not in [t.lower() for t in search_terms]:
             if ext_lower == '.gguf': deep_clean += " gguf"
             search_terms.append(deep_clean)
        
        
        # Phase 3: Token 化版本（兜底）
        tokens = AdvancedTokenizer.tokenize(cleaned_base)
        final_tokens = [t for t in tokens if t not in NOISE_SUFFIXES]
        
        if final_tokens:
            space_joined = " ".join(final_tokens)
            if ext_lower == '.gguf': space_joined += " gguf"
            if space_joined.lower() not in [t.lower() for t in search_terms]:
                search_terms.append(space_joined)
        
        # Phase 4: Chinese & Symbol Optimization (Target: "F.1" -> "Flux.1")
        # 专门处理 "好看的亚洲人脸F.1" 这种混合+简写情况
        
        # 4.1 符号归一化 (Symbol Normalization)
        # Handle "F.1", "F1", "Flux1" -> "Flux.1"
        # 使用 (?<![a-z]) 而非 \b 以兼容中文前缀 (如 "人脸F.1")
        optimized_base = re.sub(r'(?i)(?<![a-z])F[\.\s_-]?1(?![a-z0-9])', 'Flux.1', raw_stem)
        
        # 4.2 CJK 分词 (CJK Segmentation)
        # 在中文和英文/数字之间插入空格: "人脸F" -> "人脸 F"
        optimized_base = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', optimized_base)
        optimized_base = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', optimized_base)
        
        # 4.3 清洗多余符号
        optimized_base = re.sub(r'[-_.]+', ' ', optimized_base).strip()
        
        if optimized_base and len(optimized_base) > 2:
            if ext_lower == '.gguf': optimized_base += " gguf"
            
            # 只有当优化后的词与现有词不同时才添加
            if optimized_base.lower() not in [t.lower() for t in search_terms]:
                # 放在比较靠前的位置 (Priority 2)
                search_terms.insert(1, optimized_base)

        # Phase 5: 原始文件名（高精度模式）
        # 始终包含原始文件名（仅替换分隔符），保留 bf16, int8 等精确标记
        # 放在最后作为精确匹配候选项
        raw_spaced = re.sub(r'[-_.]+', ' ', base_name).strip()
        if ext_lower == '.gguf' and 'gguf' not in raw_spaced.lower():
             raw_spaced += " gguf"
             
        if raw_spaced.lower() not in [t.lower() for t in search_terms]:
            # 如果原始名很长，可能需要在前面尝试
            search_terms.append(raw_spaced)

        # === 智能去重与限制 ===
        unique_terms = []
        seen = set()
        for term in search_terms:
            t = term.strip().lower()
            if t and t not in seen and len(t) > 1:  # 过滤太短的词
                seen.add(t)
                unique_terms.append(term.strip())
        
        # 限制候选词数量
        return unique_terms[:5]

    @staticmethod
    def detect_base_model(filename):
        """
        语义识别: 检测基座模型架构
        返回: 'sdxl', 'sd15', 'sd21', 'flux', 'pony', 'qwen', 'sd3', 'hunyuan', 'auraflow', 'kwai', 'unknown'
        """
        lower = filename.lower()
        
        # 1. Pony (往往基于 SDXL 但生态独立，需优先识别)
        if "pony" in lower:
            return "pony"
            
        # 2. Flux
        # 匹配 flux, flux1, fl_ (common prefix), awportraitfl, f.1 (e.g. F.1 奶油风)
        if "flux" in lower or re.search(r'\bfl\d?[\-_]', lower) or "awportraitfl" in lower or "f.1" in lower:
            return "flux"
        
        # 3. SD3 (SD3.5, SD3)
        if re.search(r'sd3[\._]?5|sd3', lower):
            return "sd3"

        # 4. SDXL
        # 匹配 xl, sdxl, juggernaut_xl, dynavision_xl, supir
        # Expanded regex to catch suffix 'xl' like 'juggernautxl'
        # (?:[\W_]|^)xl -> start of word xl
        # xl(?:[\W_]|$) -> end of word xl
        # AND capture 'ends with xl' logic via .*xl(\.safetensors)?
        if re.search(r'(?:[\W_]|^)xl(?:[\W_]|$)|sdxl|base_1\.0|refiner|supir', lower):
            return "sdxl"
        # Case: juggernautXL (no separator). Explicit check or heuristic?
        # If 'xl' is at the end of the name part (before ext)
        base, _ = os.path.splitext(lower)
        if base.endswith("xl") and not base.endswith("pixel"):
            return "sdxl"
            
        # 5. SD1.5 / SD2.1
        if re.search(r'v1[\-._]?5|sd15|1\.5|dreamshaper|realistic_vision', lower):
            return "sd15"
        if re.search(r'v2[\-._]?1|sd21|2\.1', lower):
            return "sd21"
            
        # 6. New Gen (Hunyuan, AuraFlow, Kwai/LTX)
        if "hunyuan" in lower: return "hunyuan"
        if "aura" in lower and "flow" in lower: return "auraflow"
        if "ltx" in lower or "kolors" in lower: return "kwai"
            
        # 7. LLM/VLM based
        if "qwen" in lower: return "qwen"
        if "llama" in lower: return "llama"
        
        # 8. Default heuristics
        return "unknown"

    @staticmethod
    def detect_quantization(filename):
        """
        检测模型量化/精度版本
        返回: 'bf16', 'fp16', 'fp32', 'int8', 'q4_k_m', 'pixel', ... 或 None
        """
        lower = filename.lower()
        # Regex for specific quantizations
        # 1. GGUF Quants (Complex)
        # q4_0, q4_1, q5_0, q5_1, q8_0, q4_k, q4_k_m, q4_k_s...
        # iq1_s, iq2_xxs, sq...
        # match full pattern (q|iq|sq|tq)\d+[a-z0-9_]*
        # Allow separators: - _ .
        gguf_match = re.search(r'(?:[\W_]|^)((?:q|iq|sq|tq)\d+[a-z0-9_]*)(?:[\W_]|$)', lower)
        if gguf_match:
            return gguf_match.group(1)
            
        # 2. Precision
        if "bf16" in lower: return "bf16"
        if "fp16" in lower: return "fp16"
        if "fp32" in lower: return "fp32"
        if "fp8" in lower: return "fp8"
        if "bf16" in lower: return "bf16"
        if "f16" in lower: return "fp16" # Normalize F16 to fp16
        if "f32" in lower: return "fp32" # Normalize F32 to fp32
        if "int8" in lower: return "int8"
        if "int4" in lower: return "int4"
        
        # 3. No quant detected
        return None

    @staticmethod
    def lookup_popular_model(filename):
        """
        查找 ComfyUI 主流模型/官方模型映射
        """
        base_name = os.path.basename(filename)
        # 移除扩展名
        for ext in ['.safetensors', '.gguf', '.ckpt', '.pt', '.bin', '.pth']:
            if base_name.lower().endswith(ext):
                base_name = base_name[:-len(ext)]
                break
        
        base_lower = base_name.lower()

        # 1. 查表 (精确匹配)
        for key, repo_id in COMFYUI_POPULAR_MODELS.items():
            if base_lower == key.lower():
                return (repo_id, key)

        # 2. 查表 (模糊变体匹配)
        # 尝试移除精度后缀再匹配
        precision_suffixes = ['-fp8', '-fp16', '-bf16', '_fp8', '_fp16', '_bf16', '.fp8', '.fp16', '.bf16']
        for suffix in precision_suffixes:
            if base_lower.endswith(suffix):
                stripped = base_lower[:-len(suffix)]
                for key, repo_id in COMFYUI_POPULAR_MODELS.items():
                    if stripped == key.lower():
                        return (repo_id, key)

        return (None, None)


    @staticmethod
    def _check_flux_compatibility(name_a, name_b):
        """
        验证 Flux 模型兼容性
        Dev 与 Schnell 互斥
        """
        a = name_a.lower()
        b = name_b.lower()
        
        is_dev_a = "dev" in a
        is_schnell_a = "schnell" in a
        
        is_dev_b = "dev" in b
        is_schnell_b = "schnell" in b
        
        # 如果两边都明确指定了类型，必须一致
        if (is_dev_a or is_schnell_a) and (is_dev_b or is_schnell_b):
            if is_dev_a and not is_dev_b: return False
            if is_schnell_a and not is_schnell_b: return False
            
        return True

    @staticmethod
    def _check_sdxl_compatibility(name_a, name_b):
        """
        验证 SDXL 模型兼容性
        Base 与 Refiner 互斥
        """
        a = name_a.lower()
        b = name_b.lower()
        
        is_base_a = "base" in a
        is_refiner_a = "refiner" in a
        
        is_base_b = "base" in b
        is_refiner_b = "refiner" in b
        
        if (is_base_a or is_refiner_a) and (is_base_b or is_refiner_b):
            if is_base_a and not is_base_b: return False
            if is_refiner_a and not is_refiner_b: return False
            
        return True

    @staticmethod
    def calculate_similarity(name_a, name_b):
        """
        计算综合相似度 (Smart Rules + Jaccard + RapidFuzz)
        """
        if not name_a or not name_b: return 0.0
        
        # === 0. Semantic Architecture Check (The "Brain" Filter) ===
        base_a = AdvancedTokenizer.detect_base_model(name_a)
        base_b = AdvancedTokenizer.detect_base_model(name_b)
        
        if base_a != "unknown" and base_b != "unknown":
            if base_a != base_b:
                return 0.0
        
        # === 0.1 Strict Flux Compatibility Check ===
        if base_a == "flux" and base_b == "flux":
            if not AdvancedTokenizer._check_flux_compatibility(name_a, name_b):
                return 0.0

        # === 0.2 Strict SDXL Compatibility Check ===
        if base_a == "sdxl" and base_b == "sdxl":
             if not AdvancedTokenizer._check_sdxl_compatibility(name_a, name_b):
                return 0.0

        # === 0.5 Quantization/Precision Check (The "Strict" Filter) ===
        quant_a = AdvancedTokenizer.detect_quantization(name_a)
        quant_b = AdvancedTokenizer.detect_quantization(name_b)
        
        # 特殊处理 GGUF 仓库级匹配：
        name_a_upper = name_a.upper()
        name_b_upper = name_b.upper()
        # ... (rest of old code below) ...
        name_b_upper = name_b.upper()
        is_gguf_repo_a = (name_a_upper.endswith("-GGUF") or "/GGUF" in name_a_upper) and not quant_a
        is_gguf_repo_b = (name_b_upper.endswith("-GGUF") or "/GGUF" in name_b_upper) and not quant_b
        
        # 如果一侧是 GGUF 通配仓库，另一侧有具体量化，则跳过严格量化检测
        skip_quant_check = (is_gguf_repo_a and quant_b) or (is_gguf_repo_b and quant_a)
        
        # 只有当两边都有明确量化标记，且不一致时，才判定不兼容
        # e.g. "bf16" vs "fp16" -> Mismatch
        # e.g. "foo" vs "foo_fp16" -> Allow (one side is ambig)
        if quant_a and quant_b and not skip_quant_check:
            if quant_a != quant_b:
                return 0.0
        
        # === 0.6 One-Sided Strict Precision Check ===
        # 特殊精度 (bf16, fp8, int8) 必须严格匹配
        # 如果 A 指定了 bf16，而 B 没有指定（或指定了其他的），则不匹配
        # (fp16/fp32 较为通用，文件名常省略，故不做单侧强制)
        STRICT_PRECISIONS = {'bf16', 'fp8', 'int8', 'int4', 'q8'}
        
        # Case A: Target has strict precision, Candidate missing or different
        if quant_a in STRICT_PRECISIONS:
            if quant_b != quant_a: 
                # e.g. Target="x_bf16", Cand="x" (None) -> Mismatch
                # e.g. Target="x_bf16", Cand="x_fp16" -> Mismatch (Caught above, but safe to reiterate)
                return 0.0
                
        # Case B: Candidate has strict precision, Target missing
        # e.g. Target="x", Cand="x_bf16" -> Mismatch
        # 用户若未指定 bf16，不应给自动匹配 bf16 版本（可能显存不支持）
        if quant_b in STRICT_PRECISIONS:
            if quant_a != quant_b:
                return 0.0
        
        # === 预处理：移除仓库组织名前缀 ===
        # HuggingFace 仓库格式通常是 "org/repo-name"，例如 "unsloth/Qwen-Image-Edit-2511-GGUF"
        # 组织名对相似度匹配是噪声，应当移除
        processed_a = name_a
        processed_b = name_b
        if "/" in name_a:
            # 只保留仓库名部分 (最后一个 / 之后)
            processed_a = name_a.rsplit("/", 1)[-1]
        if "/" in name_b:
            processed_b = name_b.rsplit("/", 1)[-1]
        
        # 1. Token Similarity (Jaccard) - 使用全部 token 检测关键词冲突
        tokens_a = set(AdvancedTokenizer.tokenize(processed_a))
        tokens_b = set(AdvancedTokenizer.tokenize(processed_b))
        
        if not tokens_a or not tokens_b: return 0.0
        
        # 1.5 Critical Mismatch Check
        # 如果一侧有 Critical Term 而另一侧没有 -> 0分
        # symmetric_difference = (A - B) | (B - A)
        diff = tokens_a.symmetric_difference(tokens_b)
        critical_mismatch = diff.intersection(CRITICAL_TERMS)
        if critical_mismatch:
            # 这是一个及其严格的惩罚：只要有关键功能词不匹配，直接判定为不同模型
            # e.g. "upscale" vs "" -> mismatch
            return 0.0
        
        # 2. 核心 Token Jaccard (移除技术后缀后的匹配)
        # 这对于 GGUF 仓库匹配至关重要：排除 q4, k, s 等噪声
        core_a = AdvancedTokenizer.get_core_tokens(processed_a)
        core_b = AdvancedTokenizer.get_core_tokens(processed_b)
        
        if not core_a or not core_b:
            # 降级到普通 token 匹配
            intersection = len(tokens_a.intersection(tokens_b))
            union = len(tokens_a.union(tokens_b))
            jaccard = intersection / union if union > 0 else 0
        else:
            core_intersection = len(core_a.intersection(core_b))
            core_union = len(core_a.union(core_b))
            jaccard = core_intersection / core_union if core_union > 0 else 0
            
            # --- Chinese Optimization: Partial English Match ---
            # 如果一侧包含中文，计算 "English-Only Jaccard"
            # 假设中文部分只是描述，英文部分是核心 ID
            has_cn_a = bool(re.search(r'[\u4e00-\u9fff]', processed_a))
            has_cn_b = bool(re.search(r'[\u4e00-\u9fff]', processed_b))
            
            if has_cn_a or has_cn_b:
                # 提取纯 ASCII token (只包含英文字母和数字)
                # Helper inline function
                def get_ascii_tokens(tokens):
                    return {t for t in tokens if re.match(r'^[a-zA-Z0-9]+$', t)}
                
                ascii_a = get_ascii_tokens(core_a)
                ascii_b = get_ascii_tokens(core_b)
                
                if ascii_a and ascii_b:
                    asc_int = len(ascii_a.intersection(ascii_b))
                    asc_union = len(ascii_a.union(ascii_b))
                    # 只有当英文部分有显著重叠 (>=2 tokens or >50%) 时才采纳
                    if asc_union > 0:
                        ascii_jaccard = asc_int / asc_union
                        # 如果英文部分匹配得更好，提升 Jaccard
                        # 但不能完全替代 (避免 1.safetensors vs 1.ckpt 这种极端情况)
                        if ascii_jaccard > jaccard:
                            # 融合分数：80% English Jaccard + 20% Original
                            jaccard = (ascii_jaccard * 0.8) + (jaccard * 0.2)

            # 核心词覆盖率奖励：如果较短的一侧核心词被完全覆盖，额外加分
            smaller = core_a if len(core_a) <= len(core_b) else core_b
            coverage = len(smaller.intersection(core_a & core_b)) / len(smaller) if smaller else 0
            if coverage >= 0.9:
                # 90%+ 核心词被覆盖，额外奖励 0.15
                jaccard = min(1.0, jaccard + 0.15)
        
        # === 2.5 Significant Content Mismatch Penalty ===
        # 如果一侧包含了另一侧没有的“核心描述词”，则大幅扣分
        # 这防止 "AsianFace F.1" Matches "Flux1-dev"
        # 核心描述词定义：去除通用技术词后的所有 Token
        
        # symmetric_difference: 仅出现在其中一侧的词
        sym_diff = core_a.symmetric_difference(core_b)
        
        # 如果差异词中包含非数字/非单字母的实质性内容 -> 视为不匹配
        penalty = 0.0
        for t in sym_diff:
            # 忽略纯数字 (版本号差异通常由其他逻辑处理/容忍)
            if t.isdigit(): continue
            # 忽略极短词 (1个字母)
            if len(t) < 2: continue
            # 忽略常见连接词/通用词
            if t in {'v', 'version', 'ver', 'model', 'net', 'test'}: continue
            
            # 如果出现了额外的实质性单词 (e.g. 'asian', 'face', 'girl', 'animex')
            penalty += 0.3
            
        jaccard = max(0.0, jaccard - penalty)
        
        # 3. Sequence Similarity (用于捕捉顺序和部分匹配)
        # 使用 rapidfuzz 加速
        # 关键修改：使用归一化后的文本进行比较，以匹配 F.1 vs Flux 1
        norm_a = AdvancedTokenizer._normalize_text(processed_a)
        norm_b = AdvancedTokenizer._normalize_text(processed_b)
        
        # 如果归一化后变成空的（极少见），回退到原始
        s1 = norm_a if norm_a.strip() else processed_a.lower()
        s2 = norm_b if norm_b.strip() else processed_b.lower()

        # rapidfuzz.fuzz.ratio 返回 0-100 的分数
        seq_ratio = rf_fuzz.ratio(s1, s2) / 100.0
        # 额外使用 token_set_ratio 捕捉词汇重排序匹配
        token_ratio = rf_fuzz.token_set_ratio(s1, s2) / 100.0
        seq_ratio = max(seq_ratio, token_ratio)
        
        # 加权平均: Token 相似度通常更重要，因为文件名可能有无关前缀/后缀
        final_score = (jaccard * 0.7) + (seq_ratio * 0.3)
             
        return final_score

