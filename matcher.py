import difflib
import os

class ModelMatcher:
    def __init__(self, scanner):
        self.scanner = scanner

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

    def _tokenize(self, text):
        """将文本拆分为 token 集合 (v1.5_pruned -> {v1, 5, pruned})"""
        # 替换常见分隔符为为空格
        for char in ["_", "-", ".", " "]:
            text = text.replace(char, " ")
        # 拆分并过滤空串
        tokens = [t.lower() for t in text.split(" ") if t.strip()]
        return set(tokens)

    def _token_similarity(self, set_a, set_b):
        """计算两个 token 集合的相似度 (Jaccard Index)"""
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a.intersection(set_b))
        union = len(set_a.union(set_b))
        return intersection / union

    def match(self, missing_items):
        """
        匹配缺失的模型
        """
        matches = []
        
        # 1. Prepare Index
        index_models = self.scanner.get_all_models()
        
        full_name_map = {}
        basename_map = {}
        
        # Pre-calculate tokens for all local models to speed up fuzzy search
        # List of tuples: (model_info, token_set)
        token_index = []

        for info in index_models:
            filename = info["filename"]
            
            # 1. Full Normalized
            norm = self._normalize_name(filename)
            full_name_map[norm] = info
            full_name_map[filename.lower()] = info
            
            # 2. Basename
            base = self._get_basename(filename)
            if base not in basename_map:
                basename_map[base] = info
            
            # 3. Token Set (Only basename tokens mostly relevant?)
            # 使用 basename 的 token 会更精准，避免目录干扰
            token_set = self._tokenize(base)
            token_index.append((info, token_set))

        # Get candidates for legacy fuzzy match
        available_names = list(full_name_map.keys())

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
            
            # Priority 3: Smart Token Match (NEW)
            # Solves "v1.5_pruned" vs "v1-5-pruned"
            if not best_match:
                target_tokens = self._tokenize(target_base)
                best_score = 0.0
                best_candidate = None
                
                for info, candidate_tokens in token_index:
                    score = self._token_similarity(target_tokens, candidate_tokens)
                    if score > best_score:
                        best_score = score
                        best_candidate = info
                
                # 设置一个较高的阈值，避免错误匹配
                # 0.6 意味着大约 60% 的关键词重合
                if best_score >= 0.6:
                    best_match = best_candidate

            # Priority 4: Legacy Fuzzy Match (Full Path)
            # (Only use if token match failed or score too low)
            if not best_match:
                similars = difflib.get_close_matches(target_norm, available_names, n=1, cutoff=0.85)
                if similars:
                    best_match = full_name_map[similars[0]]

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
