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
        self._index_built = False
        self._last_model_count = -1
        
        # Pre-compile regex for performance
        import re
        self.rank_pat = re.compile(r'(?:rank|step|epoch)[-_]?(\d+)')
        self.anchor_pat = re.compile(r"(?i)^(wan\d|sdxl|pony|flux)")
        self.ver_pat = re.compile(r"(?i)^(v\d|\d+\.\d+)")

    def invalidate_index(self):
        """显式使索引失效，强制在下次匹配时重新构建"""
        self._index_built = False
        self._last_model_count = -1

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

    def _build_index(self, force=False):
        """构建倒排索引以加速匹配 (O(N) -> O(1))，具备缓存校验功能"""
        current_models = list(self.scanner.get_all_models())
        current_count = len(current_models)
        
        # 如果索引已建立且模型数量一致，且未强制刷选，则复用现有倒排索引
        if self._index_built and not force and current_count == self._last_model_count:
            return

        self.model_list = current_models
        self._last_model_count = current_count
        self.inverted_index = {}
        
        # [v3.2.0] Phase 3: 格式分区索引
        self.format_indices = {
            "gguf": set(),
            "standard": set(),
            "other": set()
        }
        
        for idx, info in enumerate(self.model_list):
            filename = info["filename"]
            
            # 1. 格式分区
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".gguf":
                self.format_indices["gguf"].add(idx)
            elif ext in {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}:
                self.format_indices["standard"].add(idx)
            else:
                self.format_indices["other"].add(idx)
            
            # 2. Token 倒排索引
            base_tokens = AdvancedTokenizer.tokenize(self._get_basename(filename))
            
            for token in base_tokens:
                if token not in self.inverted_index:
                    self.inverted_index[token] = set()
                self.inverted_index[token].add(idx)
                
        self._index_built = True

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
                    "matched_value": os.path.normpath(best_match["filename"]),
                    "path": os.path.normpath(best_match["path"]),
                    "match_type": match_type,
                    "type": best_match.get("type", "unknown")
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
        Check for hard conflicts. Returns True if conflict exists.
        Logic: Mutual Inclusion for Critical Tokens.
        If Token A is in Target, it MUST be in Candidate (and vice versa) for the match to be valid.
        """
        t_lower = target_name.lower()
        c_lower = candidate_name.lower()
        
        # [v3.2.0] Phase 1: HARD FORMAT BLOCK
        # .gguf and .safetensors/.ckpt are fundamentally different ecosystems
        FORMAT_GROUPS = {
            "gguf": {".gguf"},
            "standard": {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
        }
        
        def get_format_group(name):
            ext = os.path.splitext(name)[1].lower()
            for group, exts in FORMAT_GROUPS.items():
                if ext in exts:
                    return group
            return "other"
        
        t_group = get_format_group(target_name)
        c_group = get_format_group(candidate_name)
        
        if t_group != "other" and c_group != "other" and t_group != c_group:
            return True  # HARD CONFLICT: gguf <-> standard
        
        # 1. Critical Token Mutual Exclusion
        # If one has it, the other MUST have it.
        # Format: (TokenString, IsStrictWordBoundary)
        # For now, simple substring is effective for these specific keys
        critical_tokens = [
            "i2v", "t2v",
            "inpainting",
            "vae", # Critical: VAE vs Checkpoint
            "upscaler",
            "refiner",
            "img2vid", "txt2vid"
        ]
        
        # Helper to check presence (could be regex for boundary if needed, but filenames vary)
        # Using simple 'in' is safer for "Wan2.1_I2V" (no spaces)
        
        for token in critical_tokens:
            in_target = token in t_lower
            in_cand = token in c_lower
            
            # XOR: One has it, the other doesn't -> Conflict
            if in_target != in_cand:
                return True
                
        # 2. Mutually Exclusive Pairs (One is A, One is B -> Conflict)
        # Useful for things that aren't binary "presence" but specific alternatives
        conflict_pairs = [
            ("sdxl", "sd1.5"),
            ("mp4", "gif"),
            ("fp16", "fp8"), # User might care, but maybe fuzzy match handles score?
                             # Let's be strict for accuracy request.
            ("rank128", "rank64"), # Explicit Ranks
            ("rank128", "rank32"),
            ("rank64", "rank32"),
            ("rank83", "rank128"), # Specific user case
        ]
        
        for a, b in conflict_pairs:
            has_a_t = a in t_lower
            has_b_t = b in t_lower
            has_a_c = a in c_lower
            has_b_c = b in c_lower
            
            # If Target is A and Candidate is B -> Conflict
            if has_a_t and has_b_c: return True
            # If Target is B and Candidate is A -> Conflict
            if has_b_t and has_a_c: return True
            
        # 3. Numeric Rank/Step Extraction (General Case)
        # Extract all numbers preceded by 'rank' or 'step'
        t_nums = set(self.rank_pat.findall(t_lower))
        c_nums = set(self.rank_pat.findall(c_lower))
        
        # If both have extracted numbers, and they are disjoint -> Conflict
        if t_nums and c_nums and t_nums.isdisjoint(c_nums):
            # e.g. Target={128}, Cand={64} -> Conflict
            # e.g. Target={128}, Cand={128} -> OK
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
        
        # [v3.2.0] Phase 3: 格式预过滤
        target_ext = os.path.splitext(current_val)[1].lower()
        if target_ext == ".gguf":
            format_pool = self.format_indices.get("gguf", set())
        elif target_ext in {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}:
            format_pool = self.format_indices.get("standard", set())
        else:
            format_pool = None  # 不过滤
        
        if format_pool is not None:
            candidate_indices = candidate_indices.intersection(format_pool)
        
        if not candidate_indices:
            return None

        # Weights & Anchors
        import re
        W_ANCHOR = 10.0
        W_VERSION = 5.0
        W_NORMAL = 1.0
        W_NOISE = 0.1
        from .utils import NOISE_SUFFIXES
        
        target_anchors = {t for t in target_tokens if self.anchor_pat.match(t)}
        target_versions = {t for t in target_tokens if self.ver_pat.match(t)}
        
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
            
            # 2. [v3.2.0] Multiplicative Format Penalty (Phase 2)
            # Format mismatch = hard zero, not weak penalty
            cand_fmt = AdvancedTokenizer.get_model_format(info["filename"])
            format_multiplier = 1.0
            if target_fmt != "other" and cand_fmt != "other" and target_fmt != cand_fmt:
                format_multiplier = 0.0  # HARD ZERO
            
            # 3. [Fix] Strict Type Enforcement
            type_score = 0.0
            cand_type = info.get("type", "unknown")
            if expected_types:
                if cand_type not in expected_types:
                    continue  # Strict Skip
                type_score = 30.0 # Bonus for consistency match

            
            final_score = (base_final + type_score) * format_multiplier
            
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
        """Priority 5: RapidFuzz Backup (Replaces slow difflib)"""
        try:
            from rapidfuzz import process, fuzz
        except ImportError:
            # Fallback if rapidfuzz missing (though it's in requirements)
            import difflib
            return self._find_legacy_match_difflib(item_ctx, ctx)

        target_base = item_ctx["target_base"]
        current_val = item_ctx["current_val"]
        expected_types = item_ctx["expected_types"]
        basename_map = ctx["basename_map"]
        
        available_names = list(basename_map.keys())
        
        # Use simple ratio or partial_ratio
        # score_cutoff=85 equivalent to 0.85
        match = process.extractOne(
            target_base, 
            available_names, 
            scorer=fuzz.ratio, 
            score_cutoff=85
        )
        
        if match:
            best_name, score, idx = match
            candidate_info = basename_map[best_name]
            
            # [Fix] Apply Conflict Check
            if self._check_conflicts(current_val, candidate_info["filename"]):
                return None
            
            # Category Check
            cand_type = candidate_info.get("type", "unknown")
            if expected_types and cand_type not in expected_types:
                return None
                
            return candidate_info
            
        return None

    def _find_legacy_match_difflib(self, item_ctx, ctx):
        """Fallback for when rapidfuzz is missing"""
        target_base = item_ctx["target_base"]
        current_val = item_ctx["current_val"]
        expected_types = item_ctx["expected_types"]
        basename_map = ctx["basename_map"]
        
        available_names = list(basename_map.keys())
        similars = difflib.get_close_matches(target_base, available_names, n=1, cutoff=0.85)
        
        if similars:
            match_info = basename_map[similars[0]]
            
            # [Fix] Apply Conflict Check here too
            if self._check_conflicts(current_val, match_info["filename"]):
                return None
                
            cand_type = match_info.get("type", "unknown")
            if expected_types and cand_type not in expected_types:
                return None
            return match_info
        return None
