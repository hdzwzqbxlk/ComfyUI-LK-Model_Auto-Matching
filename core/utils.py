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

# ============================================================
# ComfyUI 官方主流模型精确映射表
# 来源: https://comfyanonymous.github.io/ComfyUI_examples/
# 格式: {模型基础名(无扩展名): HuggingFace 仓库 ID}
# ============================================================
COMFYUI_POPULAR_MODELS = {
    # === SD1.5 系列 ===
    'v1-5-pruned-emaonly': 'Comfy-Org/stable-diffusion-v1-5-archive',
    'v1-5-pruned-emaonly-fp16': 'Comfy-Org/stable-diffusion-v1-5-archive',
    'v1-5-pruned': 'Comfy-Org/stable-diffusion-v1-5-archive',
    '512-inpainting-ema': 'runwayml/stable-diffusion-inpainting',
    
    # === SDXL 系列 ===
    'sd_xl_base_1.0': 'stabilityai/stable-diffusion-xl-base-1.0',
    'sd_xl_base_1.0_0.9vae': 'stabilityai/stable-diffusion-xl-base-1.0',
    'sd_xl_refiner_1.0': 'stabilityai/stable-diffusion-xl-refiner-1.0',
    'sd_xl_refiner_1.0_0.9vae': 'stabilityai/stable-diffusion-xl-refiner-1.0',
    'sdxl_vae': 'madebyollin/sdxl-vae-fp16-fix',
    'juggernautXL_juggXIByRundiffusion': 'RunDiffusion/Juggernaut-XI-v11',
    
    # === SD3 / SD3.5 系列 ===
    'sd3_medium': 'stabilityai/stable-diffusion-3-medium',
    'sd3_medium_incl_clips': 'stabilityai/stable-diffusion-3-medium',
    'sd3.5_large': 'stabilityai/stable-diffusion-3.5-large',
    'sd3.5_large_turbo': 'stabilityai/stable-diffusion-3.5-large-turbo',
    'sd3.5_medium': 'stabilityai/stable-diffusion-3.5-medium',
    'sd3.5_large_fp8_scaled': 'Comfy-Org/stable-diffusion-3.5-fp8',
    'sd3.5_medium_incl_clips_t5xxlfp8scaled': 'Comfy-Org/stable-diffusion-3.5-fp8',
    
    # === Flux 系列 ===
    'flux1-dev': 'black-forest-labs/FLUX.1-dev',
    'flux1-schnell': 'black-forest-labs/FLUX.1-schnell',
    'flux1-dev-fp8': 'Comfy-Org/flux1-dev',
    'flux1-schnell-fp8': 'Comfy-Org/flux1-schnell',
    
    # === 文本编码器 / CLIP ===
    'clip_l': 'Comfy-Org/stable-diffusion-3.5-fp8',
    'clip_g': 'Comfy-Org/stable-diffusion-3.5-fp8',
    't5xxl': 'comfyanonymous/flux_text_encoders',
    't5xxl_fp16': 'comfyanonymous/flux_text_encoders',
    't5xxl_fp8_e4m3fn': 'comfyanonymous/flux_text_encoders',
    't5xxl_fp8_e4m3fn_scaled': 'comfyanonymous/flux_text_encoders',
    'clip_vision_g': 'comfyanonymous/clip_vision_g',
    
    # === VAE ===
    'ae': 'Comfy-Org/Lumina_Image_2.0_Repackaged',
    'vae-ft-mse-840000-ema-pruned': 'stabilityai/sd-vae-ft-mse',
    
    # === SUPIR (超分辨率) ===
    'SUPIR-v0F': 'Kijai/SUPIR_pruned',
    'SUPIR-v0F_fp16': 'Kijai/SUPIR_pruned',
    'SUPIR-v0Q': 'Kijai/SUPIR_pruned',
    'SUPIR-v0Q_fp16': 'Kijai/SUPIR_pruned',
    
    # === AuraFlow ===
    'aura_flow_0.2': 'fal/AuraFlow-v0.2',
    'aura_flow_0.3': 'fal/AuraFlow-v0.3',
    
    # === LTX-Video 系列 ===
    'ltx-video-2b-v0.9': 'Lightricks/LTX-Video',
    'ltx-2-19b-distilled': 'Lightricks/LTX-Video-0.9.7',
    'ltx-2-19b-distilled-fp8': 'Lightricks/LTX-Video-0.9.7',
    
    # === Mochi (视频模型) ===
    'mochi_preview_fp8_scaled': 'genmo/mochi-1-preview',
    'mochi_preview': 'genmo/mochi-1-preview',
    
    # === SVD (Stable Video Diffusion) ===
    'svd': 'stabilityai/stable-video-diffusion-img2vid',
    'svd_xt': 'stabilityai/stable-video-diffusion-img2vid-xt',
    'svd_xt_1_1': 'stabilityai/stable-video-diffusion-img2vid-xt-1-1',
    
    # === Audio 模型 ===
    'stable-audio-open-1_0': 'stabilityai/stable-audio-open-1.0',
    'ace_step_v1_3.5b': 'ACE-Step/ACE-Step-v1-3.5B',
    
    # === ControlNet ===
    'sd3.5_large_controlnet_canny': 'stabilityai/stable-diffusion-3.5-controlnets',
    'sd3.5_large_controlnet_depth': 'stabilityai/stable-diffusion-3.5-controlnets',
    'sd3.5_large_controlnet_blur': 'stabilityai/stable-diffusion-3.5-controlnets',
    
    # === 加速 LoRA (Hyper/LCM/TCD/Lightning) ===
    # SD1.5 加速
    'Hyper-SD15-8steps-lora': 'ByteDance/Hyper-SD',
    'LCM_LoRA_SDv15': 'latent-consistency/lcm-lora-sdv1-5',
    'TCD-SD15-LoRA': 'h1t/TCD-SD15-LoRA',
    # SDXL 加速
    'Hyper-SDXL-8steps-lora': 'ByteDance/Hyper-SD',
    'Hyper-SDXL-8steps-lora_rank1': 'ByteDance/Hyper-SD',
    'LCM_LoRA_Weights_SDXL': 'latent-consistency/lcm-lora-sdxl',
    'TCD-SDXL-LoRA': 'h1t/TCD-SDXL-LoRA',
    'sdxl_lightning_2step_lora': 'ByteDance/SDXL-Lightning',
    'sdxl_lightning_4step_lora': 'ByteDance/SDXL-Lightning',
    'sdxl_lightning_8step_lora': 'ByteDance/SDXL-Lightning',
    # Flux 加速
    'FLUX.1-Turbo-Alpha': 'alimama-creative/FLUX.1-Turbo-Alpha',
    'FLUX.1-Turbo-Alpha-LoRA-8-Step_v1': 'alimama-creative/FLUX.1-Turbo-Alpha',
    
    # === 其他热门模型 ===
    'dreamshaper_8': 'Lykon/DreamShaper',
    'realvisxl_v5.0': 'SG161222/RealVisXL_V5.0',
    'juggernaut_xl': 'RunDiffusion/Juggernaut-XL-v9',
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
# 注意：只保留真正关键的功能差异词，避免过度严格
CRITICAL_TERMS = {
    # 模型类型（必须严格区分，不同类型模型不能互相匹配）
    'vae',  # VAE 编码器/解码器，不能与主扩散模型混淆
    'lora',  # LoRA 不能与主模型混淆
    # 功能变体（必须严格区分）
    'upscale', 'upscaler', 'refiner', 'detailer',
    'inpainting', 'inpaint',
    # 加速 LoRA 关键词（Lightning/Turbo/LCM 等是特殊变体，不能与原始模型混淆）
    'lightning', 'turbo', 'lcm', 'hyper',
    '4steps', '8steps', '2steps', '1step',
    # ControlNet 类型（必须严格区分）
    'depth', 'canny', 'openpose', 'softedge', 'scribble', 'hed', 'mlsd', 'normalbae', 'seg', 'lineart',
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
    def lookup_popular_model(filename):
        """
        查找 ComfyUI 主流模型，如果匹配则返回 HuggingFace 仓库 ID
        返回: (repo_id, matched_key) 或 (None, None)
        """
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
            'k', 'm', 's',
            # 格式后缀
            'gguf', 'safetensors', 'ckpt', 'pt', 'bin', 'pth', 'onnx', 'pkl',
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
            
            # 检查是否是复杂量化标记 (q + 数字 + 可选后缀)
            # 例如 q4, q4_k, q4_k_m 等复杂模式
            if re.match(r'^q\d+[a-z0-9_]*$', part):
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
        
        # === 特殊处理：GGUF 文件 ===
        # GGUF 仓库命名规则：通常是 "模型名-GGUF"，如 "Qwen-Image-Edit-2511-GGUF"
        if ext_lower == '.gguf':
            # 移除量化标记 (Q4_K_S, Q8_0 等) 但保留模型核心名
            # 量化标记通常在最后，格式为 -Q{数字}_{字母}_{字母} 或 -Q{数字}_{数字}
            core_name = re.sub(r'[-_]Q\d+[_A-Z0-9]*$', '', base_name, flags=re.IGNORECASE)
            
            # 首选搜索词：模型名-GGUF
            gguf_search = f"{core_name}-GGUF"
            search_terms.append(gguf_search)
            
            # 备选：原始模型名（不含量化和 GGUF）
            search_terms.append(core_name)
            
            # 降级：使用连字符分隔的核心词
            core_tokens = [t for t in re.split(r'[-_]', core_name) if t]
            if core_tokens:
                search_terms.append(' '.join(core_tokens))
        
        # === 通用处理 ===
        # Phase 1: 保留原始格式（包含中文）的清洗版本
        # 只移除量化标记，保留连字符和中文
        cleaned_base = AdvancedTokenizer._strip_variant_terms(name_only)
        
        if cleaned_base and cleaned_base not in [t.lower() for t in search_terms]:
            # 保留原始连字符格式
            clean_hyphen = re.sub(r'\s+', '-', cleaned_base.strip())
            search_terms.append(clean_hyphen)
            
            # 原始格式（保留中文）
            search_terms.append(cleaned_base)
        
        # Phase 2: 中文+英文混合处理
        # 对于包含中文的文件名，提供完整的原始格式
        if re.search(r'[\u4e00-\u9fff]', base_name):
            # 替换分隔符为空格，保留中文
            spaced = re.sub(r'[-_.]+', ' ', base_name)
            # 移除量化标记
            spaced = re.sub(r'\s+Q\d+[_A-Z0-9]*\s*$', '', spaced, flags=re.IGNORECASE)
            spaced = spaced.strip()
            if spaced and spaced.lower() not in [t.lower() for t in search_terms]:
                search_terms.append(spaced)
        
        # Phase 3: Token 化版本（兜底）
        tokens = AdvancedTokenizer.tokenize(cleaned_base)
        final_tokens = [t for t in tokens if t not in NOISE_SUFFIXES]
        
        if final_tokens:
            space_joined = " ".join(final_tokens)
            if space_joined.lower() not in [t.lower() for t in search_terms]:
                search_terms.append(space_joined)
        
        # Phase 4: 原始文件名兜底
        if not search_terms:
            raw_spaced = re.sub(r'[-_.]+', ' ', base_name).strip()
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
        
        # 特殊处理 GGUF 仓库级匹配：
        # 如果候选名以 "-GGUF" 结尾（常见的 HuggingFace GGUF 仓库命名），
        # 且不含具体量化标记，则视为"通配"仓库，包含所有量化变体
        # e.g. "Qwen-Image-Edit-2511-GGUF" 仓库包含 Q4_K_S, Q8_0 等多个变体
        name_a_upper = name_a.upper()
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
            
            # 核心词覆盖率奖励：如果较短的一侧核心词被完全覆盖，额外加分
            smaller = core_a if len(core_a) <= len(core_b) else core_b
            coverage = len(smaller.intersection(core_a & core_b)) / len(smaller) if smaller else 0
            if coverage >= 0.9:
                # 90%+ 核心词被覆盖，额外奖励 0.15
                jaccard = min(1.0, jaccard + 0.15)
        
        # 3. Sequence Similarity (用于捕捉顺序和部分匹配)
        import difflib
        matcher = difflib.SequenceMatcher(None, processed_a.lower(), processed_b.lower())
        seq_ratio = matcher.ratio()
        
        # 加权平均: Token 相似度通常更重要，因为文件名可能有无关前缀/后缀
        return (jaccard * 0.7) + (seq_ratio * 0.3)
