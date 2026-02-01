import difflib
import os
try:
    from .utils import AdvancedTokenizer
except ImportError:
    from utils import AdvancedTokenizer

class ModelMatcher:
    def __init__(self, scanner):
        self.scanner = scanner
        # 倒排索引: {token: set(model_indices)}
        self.inverted_index = {}
        self.model_list = [] # List storing actual model info, referenced by index

    def _normalize_name(self, name):
        """标准化模型名称，移除扩展名并转小写"""
        base, _ = os.path.splitext(name)
        return base.lower().strip()

    def _get_basename(self, path):
        """提取纯文件名 (不含目录，不含扩展名)"""
        # handle both / and \ just in case
        name = os.path.basename(path.replace("\\", "/"))
        base, _ = os.path.splitext(name)
        return base.lower().strip()

    def _build_index(self):
        """构建倒排索引以加速匹配 (O(N) -> O(1))"""
        self.model_list = list(self.scanner.get_all_models())
        self.inverted_index = {}
        
        for idx, info in enumerate(self.model_list):
            filename = info["filename"]
            
            # 使用 AdvancedTokenizer
            # 1. 对完整文件名 (无后缀) 分词
            base_tokens = AdvancedTokenizer.tokenize(self._get_basename(filename))
            
            # 2. 对路径进行简单分词 (可选，防止干扰太大暂不深入)
            
            for token in base_tokens:
                if token not in self.inverted_index:
                    self.inverted_index[token] = set()
                self.inverted_index[token].add(idx)

    def match(self, missing_items):
        """
        匹配缺失的模型
        """
        matches = []
        
        # 每次匹配前重建索引? 为了性能，最好缓存。
        # 但考虑到文件可能变动，且构建速度很快 (几千个文件毫秒级)，每次重建是可以接受的，或者在 scanner 变动时重建。
        # 为了简单和一致性，这里每次重建 (因为 scanner 数据是动态的)。
        self._build_index()
        
        # 辅助映射: 快速精确查找
        full_name_map = {}
        basename_map = {}
        for idx, info in enumerate(self.model_list):
             filename = info["filename"]
             norm = self._normalize_name(filename)
             full_name_map[norm] = info
             full_name_map[filename.lower()] = info
             
             base = self._get_basename(filename)
             if base not in basename_map:
                 basename_map[base] = info

        for item in missing_items:
            current_val = item.get("current")
            if not current_val:
                continue
                
            # [Filter] Skip non-model files (images, audio, etc)
            from .scanner import is_valid_model_file
            if not is_valid_model_file(current_val):
                continue

            target_norm = self._normalize_name(current_val)
            target_base = self._get_basename(current_val)
            
            best_match = None
            
            # Priority 1: Exact Full Path Match
            if target_norm in full_name_map:
                best_match = full_name_map[target_norm]
                match_type = "Exact"
            elif current_val.lower() in full_name_map:
                best_match = full_name_map[current_val.lower()]
                match_type = "Exact"
            
            # Priority 2: Exact Basename Match
            elif target_base in basename_map:
                best_match = basename_map[target_base]
                match_type = "Exact"
            
            else:
                match_type = "Fuzzy"
            
            # Priority 3: Inverted Index Fuzzy Match (Optimization)
            # This handles small typos or differences
            # Prepare Target Format for Strict Checking
            target_fmt = AdvancedTokenizer.get_model_format(current_val)
            if target_fmt == "other":
                # Try to infer from usage or assume checkpoint if unclear, but safer to match 'other' loosely
                if "gguf" in target_base.lower(): target_fmt = "gguf"
                elif ".safetensors" in current_val or ".ckpt" in current_val: target_fmt = "checkpoint"

            if not best_match:
                best_token_score = 0.0
                token_candidate_info = None
                
                target_tokens = AdvancedTokenizer.tokenize(target_base)
                candidate_indices = set()
                for token in target_tokens:
                    if token in self.inverted_index:
                        candidate_indices.update(self.inverted_index[token])
                
                # [v2.0] Weighted Scoring Algorithm
                import re
                
                # 定义权重
                W_ANCHOR = 10.0   # 强语义锚点 (Wan2.1, Pony, SDXL)
                W_VERSION = 5.0   # 版本号 (v1.5, 2.1)
                W_NORMAL = 1.0    # 普通词
                W_NOISE = 0.1     # 噪音 (fp16, pruned)

                # 识别 Target 中的关键 Token
                target_anchors = {t for t in target_tokens if re.match(r"(?i)^(wan\d|sdxl|pony|flux)", t)}
                target_versions = {t for t in target_tokens if re.match(r"(?i)^(v\d|\d+\.\d+)", t)}
                
                # 获取噪音集合 (引用 utils 中的常量)
                from .utils import NOISE_SUFFIXES

                if candidate_indices:
                    for idx in candidate_indices:
                        candidate_info = self.model_list[idx]
                        cand_filename = candidate_info["filename"]
                        cand_base = self._get_basename(cand_filename)
                        cand_tokens = set(AdvancedTokenizer.tokenize(cand_base))
                        
                        # [Strict Check] Format Compatibility
                        cand_fmt = AdvancedTokenizer.get_model_format(cand_filename)
                        
                        # 格式不匹配惩罚 (Penalty)
                        format_penalty = 0.0
                        if target_fmt != "other" and cand_fmt != "other":
                             if target_fmt != cand_fmt:
                                 # 格式不同扣分 (但不完全排除，因为 float16 vs float32 可能是同一模型)
                                 format_penalty = 2.0 
                        
                        # 计算加权分数
                        score = 0.0
                        
                        for token in target_tokens:
                            if token in cand_tokens:
                                if token in target_anchors:
                                    score += W_ANCHOR
                                elif token in target_versions:
                                    score += W_VERSION
                                elif token in NOISE_SUFFIXES:
                                    score += W_NOISE
                                else:
                                    score += W_NORMAL
                        
                        # 归一化 (Normalization)
                        # 基于 Target 的最大可能得分
                        max_possible_score = 0.0
                        for token in target_tokens:
                            if token in target_anchors: max_possible_score += W_ANCHOR
                            elif token in target_versions: max_possible_score += W_VERSION
                            elif token in NOISE_SUFFIXES: max_possible_score += W_NOISE
                            else: max_possible_score += W_NORMAL
                        
                        if max_possible_score > 0:
                            # 转换为 0-100 分
                            final_score = (score / max_possible_score) * 100
                            final_score -= format_penalty
                        else:
                            final_score = 0

                        if final_score > best_token_score:
                            best_token_score = final_score
                            token_candidate_info = candidate_info
                
                # v2.0 Strict Threshold: 提高阈值，因为加权算法更精准
                if best_token_score >= 60.0:
                    best_match = token_candidate_info

            # Priority 4: Variant Match (Cross-Quantization)
            # e.g., "Qwen...bf16.safetensors" vs "Qwen...fp16.safetensors"
            # BUT: Strict format check (GGUF != Safetensors)
            if not best_match:
                # 提取核心 Token (去除量化、格式后缀)
                target_core = AdvancedTokenizer.get_core_tokens(target_base)
                # target_fmt ALREADY DEFINED above
                
                if target_core: # 只有存在核心词时才尝试
                    best_variant_score = 0.0
                    variant_candidate = None
                    
                    variant_indices = set()
                    for token in target_core:
                        if token in self.inverted_index:
                            variant_indices.update(self.inverted_index[token])
                    
                    if variant_indices:
                        for idx in variant_indices:
                            candidate_info = self.model_list[idx]
                            candidate_filename = candidate_info["filename"]
                            
                            # Strict Format Check
                            cand_fmt = AdvancedTokenizer.get_model_format(candidate_filename)
                            # e.g. GGUF can only match GGUF
                            if target_fmt != "other" and cand_fmt != "other" and target_fmt != cand_fmt:
                                continue
                            
                            candidate_base = self._get_basename(candidate_filename)
                            
                            # 提取候选的核心词
                            candidate_core = AdvancedTokenizer.get_core_tokens(candidate_base)
                            if not candidate_core: continue
                            
                            # 计算核心词 Jaccard 相似度
                            intersection = len(target_core.intersection(candidate_core))
                            union = len(target_core.union(candidate_core))
                            core_score = intersection / union if union > 0 else 0.0
                            
                            # 要求极高的核心词重合度
                            if core_score > best_variant_score:
                                best_variant_score = core_score
                                variant_candidate = candidate_info
                        
                        # 如果核心词几乎完全一致 (>0.9)，则认为是变体匹配
                        if best_variant_score >= 0.9:
                             best_match = variant_candidate

            # Priority 5: Legacy Fuzzy Match (如果 Token 索引也没找到)
            if not best_match:
                available_names = list(basename_map.keys())
                similars = difflib.get_close_matches(target_base, available_names, n=1, cutoff=0.85)
                if similars:
                    best_match = basename_map[similars[0]]

            if best_match:
                if best_match["filename"] != current_val:
                    matches.append({
                        "id": item["id"],
                        "node_type": item["node_type"],
                        "widget_name": item["widget_name"],
                        "original_value": current_val,
                        "matched_value": best_match["filename"],
                        "path": best_match["path"],
                        "match_type": match_type
                    })

        return matches
