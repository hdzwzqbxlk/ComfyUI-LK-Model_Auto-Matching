import re
import os

# 噪声后缀词（仅过滤纯技术后缀，不过滤版本号和模型组件名）
NOISE_SUFFIXES = {
    # 精度格式
    'fp16', 'fp32', 'bf16', 'int8', 'int4', 'q4', 'q8', 'gguf', 'f16', 'f32',
    # 训练变体
    'pruned', 'ema', 'emaonly', 'noembed', 'noema',
    # 文件扩展名
    'safetensors', 'ckpt', 'pt', 'bin', 'pth', 'onnx', 'pkl',
    # 修复/最终版本
    'fix', 'fixed', 'final', 'official', 'release',
    # 内容分级
    'sfw', 'nsfw',
    # 速度优化变体
    'lightning', '8steps', '4steps', '2steps', 'turbo', 'lcm', 'hyper',
}

# 核心模型词保护列表（这些词永远不会被过滤）
PROTECTED_TERMS = {
    # SD 系列
    'sd', 'sd15', 'sd21', 'sd3', 'sdxl', 'stable', 'diffusion',
    'base', 'refiner',  # SDXL 组件
    # FLUX 系列
    'flux', 'flux1', 'schnell', 'dev',
    # 模型类型
    'vae', 'unet', 'lora', 'controlnet', 'clip', 'embeddings',
    # 其他常见模型
    'qwen', 'llama', 'mistral', 'realvis', 'juggernaut',
    'inpainting',  # 功能变体
}

# 常见模型族识别模式（用于智能搜索词生成）
MODEL_PATTERNS = {
    # (匹配模式, 替代搜索词)
    r'v1[\-_\.]?5': 'stable diffusion 1.5',
    r'v2[\-_\.]?1': 'stable diffusion 2.1',
    r'sd[\-_]?xl': 'stable diffusion xl',
    r'sd[\-_]?3': 'stable diffusion 3',
    r'flux[\-_\.]?1': 'flux.1',
}

# 常见模型名缩写映射（帮助搜索标准化）
MODEL_ALIASES = {
    'sdxl': 'stable diffusion xl',
    'sd15': 'stable diffusion 1.5',
    'sd21': 'stable diffusion 2.1',
    'sd': 'stable diffusion',
    'flux': 'flux',
    'realvis': 'realvisxl',
    'jugg': 'juggernaut',
    'qwen': 'qwen',
}

# 变体后缀：需要被“剥离”以提取核心模型名的术语
# 包括量化 (Q4_K, bf16), 格式 (gguf, safetensors), 以及功能变体 (lightning, inpainting)
VARIANT_SUFFIXES = {
    # Quantization
    'q4', 'q5', 'q8', 'q6', 'q3', 'k', 'm', 's', 'km', 'ks', 'kp',
    'q4_0', 'q4_1', 'q5_0', 'q5_1', 'q8_0', 'q4_k', 'q4_k_m', 'q4_k_s', 
    'bf16', 'fp16', 'fp32', 'int8', 'int4',
    # Format
    'gguf', 'safetensors', 'ckpt', 'pt', 'bin', 'pth', 'onnx',
    # Training
    'pruned', 'ema', 'emaonly', 'full',
    # Speed/Type
    'lightning', 'turbo', 'hyper', 'lcm', 'simpo',
    'inpainting', 'depth', 'canny', 'openpose',
}

# 核心功能词保护列表（如果这些词在一边有而另一边没有，则视为不同模型）
CRITICAL_TERMS = {
    'upscale', 'upscaler', 'refiner', 'detailer',
    'inpainting', 'inpaint',
    'depth', 'canny', 'openpose', 'softedge', 'scribble', 'hed', 'mlsd', 'normalbae', 'seg', 'lineart',
    'lora', 'lycoris', 'hypernetwork', 'embedding',
    'motion', 'animate', 'video',
}

class AdvancedTokenizer:
    """
    统一的智能分词器，用于本地匹配和网络搜索
    """
    
    @staticmethod
    def tokenize(text):
        """
        将文本拆分为 token 集合 (支持数字分离: flux1 -> flux 1)
        """
        text = text.lower()
        # 替换常见分隔符
        for char in ['_', '-', '.', ' ', '/', '\\', '[', ']', '(', ')']:
            text = text.replace(char, ' ')
        
        tokens = []
        for part in text.split():
            # split alpha and numeric (e.g., flux1 -> flux, 1)
            # 但保留纯版本号如 1.5 已经在前面把 . 替换了，变 1 5
            sub_tokens = re.findall(r'[a-z]+|\d+', part)
            if sub_tokens:
                tokens.extend(sub_tokens)
            else:
                tokens.append(part)
                
        # 过滤极短 token，但保留单个数字 (如 '1' in 'flux 1')
        ordered_tokens = []
        seen = set()
        for t in tokens:
            s = t.strip()
            if s and s not in seen:
                seen.add(s)
                ordered_tokens.append(s)
        return ordered_tokens

    @staticmethod
    def _strip_variant_terms(text):
        """
        使用 Regex 移除文件名中的技术/变体术语
        返回清洗后的字符串 (保留原有的非技术分隔符)
        """
        text = text.lower()
        base, _ = os.path.splitext(text)
        
        # 定义需要移除的正则模式
        patterns = [
            # Quantization: q4_k_m, q4_0, q5_1, q8, bf16, fp16, int8, etc.
            r'(?:^|[\-_.\s])(?:q\d+[a-z0-9_]*|f\d+|bf\d+|fp\d+|int\d+)(?:$|[\-_.\s])',
            # Common technical terms
            r'(?:^|[\-_.\s])(?:pruned|ema|emaonly|noema|full|safetensors|gguf|ckpt|pt|bin|pth|onnx)(?:$|[\-_.\s])',
            # Speed/Variant terms (removed critical terms like inpainting/depth from here)
            r'(?:^|[\-_.\s])(?:lightning|turbo|hyper|lcm|simpo)(?:$|[\-_.\s])',
        ]
        
        cleaned = base
        # 反复执行直到没有匹配
        for _ in range(2):
            for p in patterns:
                # 替换为空格，避免粘连
                cleaned = re.sub(p, ' ', cleaned)
        
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
        从文件名中提取多个候选搜索词（智能提取算法）
        """
        search_terms = []
        name_only = os.path.basename(filename)
        base_name, _ = os.path.splitext(name_only)
        normalized_name = base_name.lower()
        
        # 0.5 Raw Exact Match (Highest Priority for Specific Files)
        # e.g. "qwen-image-edit-2511-Q4_K_S.gguf" -> "qwen image edit 2511 Q4 K S"
        # Don't strip variants here! User wants exact file.
        raw_spaced = re.sub(r'[\-_.]+', ' ', base_name).strip()
        search_terms.append(raw_spaced)

        # 1. 检查模型模式 (Pattern Matching) - 优先级最高
        for pattern_str, replacement in MODEL_PATTERNS.items():
            if re.search(pattern_str, normalized_name):
                search_terms.append(replacement)
        
        # 2. 智能清洗 (Regex Stripping)
        # 这会保留原始分隔符 (如 qwen_image_edit_2511)
        cleaned_base = AdvancedTokenizer._strip_variant_terms(name_only)
        
        # 策略 A: 原始清洗串 (保留下划线/连字符)
        # e.g., "qwen_image_edit_2511"
        if cleaned_base and cleaned_base != normalized_name:
             # 去除首尾可能残留的符号
             clean_str = re.sub(r'^[\-_.]+|[\-_.]+$', '', cleaned_base.strip())
             if clean_str:
                search_terms.append(clean_str)

        # 策略 B: 纯空格分隔 (Standard)
        # e.g., "qwen image edit 2511"
        tokens = AdvancedTokenizer.tokenize(cleaned_base)
        # 过滤掉 Protected Terms 和 Noise (虽然 _strip 已经做了大部分，但 tokenize 还会拆分)
        final_tokens = []
        for t in tokens:
            if t in NOISE_SUFFIXES: continue # Double check
            final_tokens.append(t)
            
        if final_tokens:
            space_joined = " ".join(final_tokens)
            if space_joined not in search_terms:
                search_terms.append(space_joined)
                
            # 策略 C: 强制下划线分隔 (针对某些且仅支持 snake_case 的索引)
            underscore_joined = "_".join(final_tokens)
            if underscore_joined != space_joined and underscore_joined not in search_terms:
                search_terms.append(underscore_joined)
        
        # 3. 降级策略: 核心词截断
        if len(final_tokens) > 3:
            search_terms.append(" ".join(final_tokens[:3]))
        if len(final_tokens) > 2:
            search_terms.append(" ".join(final_tokens[:2]))
            
        # 4. Fallback
        if not search_terms:
            search_terms.append(normalized_name)

        # 去重并保持顺序
        unique_terms = []
        seen = set()
        for term in search_terms:
            t = term.strip()
            if t and t not in seen:
                seen.add(t)
                unique_terms.append(t)
                
        return unique_terms

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
        # match full pattern q\d+[a-z0-9_]*
        # Allow separators: - _ .
        gguf_match = re.search(r'(?:[\W_]|^)(q\d+[a-z0-9_]*)(?:[\W_]|$)', lower)
        if gguf_match:
            return gguf_match.group(1)
            
        # 2. Precision
        if "bf16" in lower: return "bf16"
        if "fp16" in lower: return "fp16"
        if "fp32" in lower: return "fp32"
        if "fp8" in lower: return "fp8"
        if "int8" in lower: return "int8"
        if "int4" in lower: return "int4"
        
        # 3. No quant detected
        return None

    @staticmethod
    def calculate_similarity(name_a, name_b):
        """
        计算综合相似度 (Jaccard + Sequence + Semantic + Quantization)
        """
        if not name_a or not name_b: return 0.0
        
        # === 0. Semantic Architecture Check (The "Brain" Filter) ===
        base_a = AdvancedTokenizer.detect_base_model(name_a)
        base_b = AdvancedTokenizer.detect_base_model(name_b)
        
        if base_a != "unknown" and base_b != "unknown":
            if base_a != base_b:
                return 0.0

        # === 0.5 Quantization/Precision Check (The "Strict" Filter) ===
        quant_a = AdvancedTokenizer.detect_quantization(name_a)
        quant_b = AdvancedTokenizer.detect_quantization(name_b)
        
        # 只有当两边都有明确量化标记，且不一致时，才判定不兼容
        # e.g. "bf16" vs "fp16" -> Mismatch
        # e.g. "foo" vs "foo_fp16" -> Allow (one side is ambig)
        if quant_a and quant_b:
            if quant_a != quant_b:
                return 0.0
        
        # 1. Token Similarity (Jaccard)
        # tokenize now returns list, convert to set
        tokens_a = set(AdvancedTokenizer.tokenize(name_a))
        tokens_b = set(AdvancedTokenizer.tokenize(name_b))
        
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
        
        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        jaccard = intersection / union if union > 0 else 0
        
        # 2. Sequence Similarity (用于捕捉顺序和部分匹配)
        import difflib
        matcher = difflib.SequenceMatcher(None, name_a.lower(), name_b.lower())
        seq_ratio = matcher.ratio()
        
        # 加权平均: Token 相似度通常更重要，因为文件名可能有无关前缀/后缀
        return (jaccard * 0.7) + (seq_ratio * 0.3)
