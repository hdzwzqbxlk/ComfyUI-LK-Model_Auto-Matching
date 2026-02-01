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
        匹配缺失的模型 (Refactored for Clean Code)
        """
        matches = []
        self._build_index()
        
        # Build maps one time
        full_name_map = {}
        basename_map = {}
        for info in self.model_list:
            filename = info["filename"]
            full_name_map[self._normalize_name(filename)] = info
            full_name_map[filename.lower()] = info
            base = self._get_basename(filename)
            if base not in basename_map:
                basename_map[base] = info
        
        # Prepare Context
        ctx = {
            "full_name_map": full_name_map,
            "basename_map": basename_map,
            "WIDGET_TO_TYPE": {
                "ckpt_name": ["checkpoints", "unet", "diffusion_models"],
                "lora_name": ["loras"],
                "vae_name": ["vae"],
                "clip_name": ["clip"],
                "control_net_name": ["controlnet", "t2i_adapter"],
                "upscale_model_name": ["upscale_models"],
                "embeddings_name": ["embeddings"],
                "style_model_name": ["style_models"],
                "hypernetwork_name": ["hypernetworks"],
                "gligen_name": ["gligen"],
            }
        }

        for item in missing_items:
            current_val = item.get("current")
            if not current_val: continue
            
            # [Filter] Skip non-model files
            from .scanner import is_valid_model_file
            if not is_valid_model_file(current_val): continue
            
            # Prepare Item Context
            item_ctx = {
                "current_val": current_val,
                "target_norm": self._normalize_name(current_val),
                "target_base": self._get_basename(current_val),
                "widget_name": item.get("widget_name", ""),
                "expected_types": ctx["WIDGET_TO_TYPE"].get(item.get("widget_name", ""), [])
            }
            
            best_match = None
            match_type = "Unknown"
            
            # 1. Exact Match
            exact = self._find_exact_match(item_ctx, ctx)
            if exact:
                best_match = exact
                match_type = "Exact"
            
            # 2. Fuzzy Match
            if not best_match:
                fuzzy = self._find_fuzzy_match(item_ctx)
                if fuzzy:
                    best_match = fuzzy
                    match_type = "Fuzzy"
            
            # 3. Variant Match
            if not best_match:
                variant = self._find_variant_match(item_ctx)
                if variant:
                    best_match = variant
                    match_type = "Variant"
            
            # 4. Legacy Match
            if not best_match:
                legacy = self._find_legacy_match(item_ctx, ctx)
                if legacy:
                    best_match = legacy
                    match_type = "Fuzzy" # Legacy is technically fuzzy

            if best_match:
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

    def _find_exact_match(self, item_ctx, ctx):
        """Priority 1 & 2: Exact Full Path or Basename Match"""
        target_norm = item_ctx["target_norm"]
        current_val = item_ctx["current_val"]
        target_base = item_ctx["target_base"]
        full_name_map = ctx["full_name_map"]
        basename_map = ctx["basename_map"]

        if target_norm in full_name_map:
            return full_name_map[target_norm]
        elif current_val.lower() in full_name_map:
            return full_name_map[current_val.lower()]
        elif target_base in basename_map:
            return basename_map[target_base]
        return None

    def _check_conflicts(self, target_name, candidate_name):
        """
        Check for hard conflicts that should disqualify a match.
        Returns True if conflict exists (should disqualify), False otherwise.
        """
        t_lower = target_name.lower()
        c_lower = candidate_name.lower()
        
        # 1. Critical Token Conflicts (Mutually Exclusive)
        conflict_pairs = [
            ("t2v", "i2v"),        # Text-to-Video vs Image-to-Video
            ("mp4", "gif"),
            ("sdxl", "sd1.5"),
            ("inpainting", "base"), # Inpainting vs Base models
            ("refiner", "base"),
        ]
        
        for a, b in conflict_pairs:
            # Check for conflicting tokens
            has_a_t = a in t_lower
            has_b_t = b in t_lower
            
            has_a_c = a in c_lower
            has_b_c = b in c_lower
            
            # Case: Target is T2V, Candidate is I2V (and not T2V) -> Conflict
            if has_a_t and not has_b_t and has_b_c and not has_a_c:
                return True
            if has_b_t and not has_a_t and has_a_c and not has_b_c:
                return True
                
        # 2. Rank/Version/Step Numeric Conflict
        # Extract "rankXXX" or "stepXXX"
        import re
        patterns = [
            r'rank[-_]?(\d+)',
            r'step[-_]?(\d+)',
            r'epoch[-_]?(\d+)'
        ]
        
        for pat in patterns:
            t_vals = re.findall(pat, t_lower)
            c_vals = re.findall(pat, c_lower)
            if t_vals and c_vals:
                # If both define a rank/step, and they differ, it's a mismatch
                if set(t_vals) != set(c_vals):
                    return True

        return False

    def _find_fuzzy_match(self, item_ctx):
        """Priority 3: Token-based Fuzzy Match with Weights"""
        current_val = item_ctx["current_val"]
        target_base = item_ctx["target_base"]
        expected_types = item_ctx["expected_types"]
        
        target_tokens = AdvancedTokenizer.tokenize(target_base)
        candidate_indices = set()
        for token in target_tokens:
            if token in self.inverted_index:
                candidate_indices.update(self.inverted_index[token])
        
        if not candidate_indices:
            return None

        # Weights & Anchors
        import re
        W_ANCHOR = 10.0
        W_VERSION = 5.0
        W_NORMAL = 1.0
        W_NOISE = 0.1
        from .utils import NOISE_SUFFIXES
        
        target_anchors = {t for t in target_tokens if re.match(r"(?i)^(wan\d|sdxl|pony|flux)", t)}
        target_versions = {t for t in target_tokens if re.match(r"(?i)^(v\d|\d+\.\d+)", t)}
        
        target_fmt = AdvancedTokenizer.get_model_format(current_val)
        if target_fmt == "other":
            if "gguf" in target_base.lower(): target_fmt = "gguf"
            elif ".safetensors" in current_val or ".ckpt" in current_val: target_fmt = "checkpoint"

        # Calculate Max Score for Normalization
        max_possible_score = 0.0
        for token in target_tokens:
            if token in target_anchors: max_possible_score += W_ANCHOR
            elif token in target_versions: max_possible_score += W_VERSION
            elif token in NOISE_SUFFIXES: max_possible_score += W_NOISE
            else: max_possible_score += W_NORMAL
        
        if max_possible_score <= 0: return None

        best_score = 0.0
        best_candidate = None

        for idx in candidate_indices:
            info = self.model_list[idx]
            
            # [Optimization] Quick conflict check before expensive token calc
            if self._check_conflicts(current_val, info["filename"]):
                continue
            
            cand_base = self._get_basename(info["filename"])
            cand_tokens = set(AdvancedTokenizer.tokenize(cand_base))
            
            # 1. Base Score
            score = 0.0
            for token in target_tokens:
                if token in cand_tokens:
                    if token in target_anchors: score += W_ANCHOR
                    elif token in target_versions: score += W_VERSION
                    elif token in NOISE_SUFFIXES: score += W_NOISE
                    else: score += W_NORMAL
            
            base_final = (score / max_possible_score) * 100
            
            # 2. Penalties
            cand_fmt = AdvancedTokenizer.get_model_format(info["filename"])
            format_penalty = 0.0
            if target_fmt != "other" and cand_fmt != "other" and target_fmt != cand_fmt:
                format_penalty = 2.0
            
            # 3. Type Bonuses
            type_score = 0.0
            cand_type = info.get("type", "unknown")
            if expected_types:
                if cand_type in expected_types: type_score = 30.0
                else: type_score = -50.0
            
            final_score = base_final - format_penalty + type_score
            
            if final_score > best_score:
                best_score = final_score
                best_candidate = info
        
        if best_score >= 60.0:
            return best_candidate
        return None

    def _find_variant_match(self, item_ctx):
        """Priority 4: Variant Match (Core Tokens Jaccard)"""
        target_base = item_ctx["target_base"]
        current_val = item_ctx["current_val"]
        expected_types = item_ctx["expected_types"]
        
        target_core = AdvancedTokenizer.get_core_tokens(target_base)
        if not target_core: return None
        
        target_fmt = AdvancedTokenizer.get_model_format(current_val)
        
        variant_indices = set()
        for token in target_core:
            if token in self.inverted_index:
                variant_indices.update(self.inverted_index[token])
        
        if not variant_indices: return None

        best_score = 0.0
        best_candidate = None

        for idx in variant_indices:
            info = self.model_list[idx]
            
            # [Optimization] Conflict Check
            if self._check_conflicts(current_val, info["filename"]):
                continue
            
            # Category Check
            cand_type = info.get("type", "unknown")
            if expected_types and cand_type not in expected_types:
                continue
            
            # Format Check
            cand_fmt = AdvancedTokenizer.get_model_format(info["filename"])
            if target_fmt != "other" and cand_fmt != "other" and target_fmt != cand_fmt:
                continue
                
            cand_base = self._get_basename(info["filename"])
            cand_core = AdvancedTokenizer.get_core_tokens(cand_base)
            if not cand_core: continue
            
            intersection = len(target_core.intersection(cand_core))
            union = len(target_core.union(cand_core))
            core_score = intersection / union if union > 0 else 0.0
            
            if core_score > best_score:
                best_score = core_score
                best_candidate = info
        
        if best_score >= 0.9:
            return best_candidate
        return None

    def _find_legacy_match(self, item_ctx, ctx):
        """Priority 5: Difflib Backup"""
        target_base = item_ctx["target_base"]
        expected_types = item_ctx["expected_types"]
        basename_map = ctx["basename_map"]
        
        available_names = list(basename_map.keys())
        similars = difflib.get_close_matches(target_base, available_names, n=1, cutoff=0.85)
        
        if similars:
            match = basename_map[similars[0]]
            cand_type = match.get("type", "unknown")
            if expected_types and cand_type not in expected_types:
                return None
            return match
        return None
