import difflib
import os

class ModelMatcher:
    def __init__(self, scanner):
        self.scanner = scanner
        # 简单的内存缓存
        self._cached_models = None

    def refresh_models(self):
        self._cached_models = self.scanner.scan_all_models()

    def _normalize_name(self, name):
        """
        标准化文件名：转小写，统一路径分隔符，可以用于模糊对比
        """
        return name.lower().replace("\\", "/")

    def match(self, target_name, model_type, threshold=0.7):
        """
        在指定模型类型中查找匹配项
        :param target_name: 工作流中丢失的模型名 (e.g. "SD1.5/v1-5-pruned.ckpt")
        :param model_type: 模型类型 (e.g. "checkpoints")
        :param threshold: 模糊匹配阈值 (0.0 - 1.0)
        :return: 最佳匹配的文件名 (e.g. "v1-5-pruned.ckpt") 或 None
        """
        if not self._cached_models:
            self.refresh_models()

        available_files = self._cached_models.get(model_type, [])
        if not available_files:
            return None

        target_base = os.path.basename(target_name)
        target_norm = self._normalize_name(target_name)
        target_base_norm = self._normalize_name(target_base)

        # Strategy 1: Exact Match (文件名完全一致，忽略原始路径)
        # 很多时候别人工作流里的路径结构跟本地不同，但文件名是一样的
        for f in available_files:
            f_base = os.path.basename(f)
            if self._normalize_name(f) == target_norm: 
                # 路径+文件名完全一致（极少见的情况，通常不需要修）
                return f
            if self._normalize_name(f_base) == target_base_norm:
                # 文件名一致，路径不同 -> High Confidence Match
                return f

        # Strategy 2: Fuzzy Match (文件名相似)
        if threshold > 0:
            # 使用 difflib 比较文件名部分的相似度 (忽略扩展名，以免 .safetensors 占权重过大)
            best_match = None
            best_ratio = 0.0
            
            target_stem = os.path.splitext(target_base_norm)[0]
            
            for f in available_files:
                f_base = os.path.basename(f)
                f_base_norm = self._normalize_name(f_base)
                f_stem = os.path.splitext(f_base_norm)[0]
                
                ratio = difflib.SequenceMatcher(None, target_stem, f_stem).ratio()
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_match = f
            
            if best_ratio >= threshold:
                return best_match
                
        return None
