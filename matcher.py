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

            target_norm = self._normalize_name(current_val)
            target_base = self._get_basename(current_val)
            
            best_match = None
            
            # Priority 1: Exact Full Path Match
            if target_norm in full_name_map:
                best_match = full_name_map[target_norm]
            elif current_val.lower() in full_name_map:
                best_match = full_name_map[current_val.lower()]
            
            # Priority 2: Exact Basename Match
            elif target_base in basename_map:
                best_match = basename_map[target_base]
            
            # Priority 3: Inverted Index Fuzzy Match (Optimization)
            # This handles small typos or differences
            if not best_match:
                target_tokens = AdvancedTokenizer.tokenize(target_base)
                candidate_indices = set()
                for token in target_tokens:
                    if token in self.inverted_index:
                        candidate_indices.update(self.inverted_index[token])
                
                best_token_score = 0.0
                token_candidate_info = None

                if candidate_indices:
                    for idx in candidate_indices:
                        candidate_info = self.model_list[idx]
                        candidate_base = self._get_basename(candidate_info["filename"])
                        
                        score = AdvancedTokenizer.calculate_similarity(target_base, candidate_base)
                        if score > best_token_score:
                            best_token_score = score
                            token_candidate_info = candidate_info
                    
                    # Strict threshold for fuzzy
                    if best_token_score >= 0.6:
                        best_match = token_candidate_info

            # Priority 4: Variant Match (Cross-Quantization)
            # e.g., "Qwen...bf16.safetensors" vs "Qwen...fp16.safetensors"
            # BUT: Strict format check (GGUF != Safetensors)
            if not best_match:
                # 提取核心 Token (去除量化、格式后缀)
                target_core = AdvancedTokenizer.get_core_tokens(target_base)
                target_fmt = AdvancedTokenizer.get_model_format(current_val) # current_val logic
                
                # 如果 current_val 没有后缀(例如ComfyUI传递的名字不带后缀?), 尝试从 base 推断
                if target_fmt == "other":
                    target_fmt = AdvancedTokenizer.get_model_format(target_base + ".safetensors") # Default assumption?
                    if "gguf" in target_base.lower(): target_fmt = "gguf"

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
                        "path": best_match["path"] 
                    })

        return matches
