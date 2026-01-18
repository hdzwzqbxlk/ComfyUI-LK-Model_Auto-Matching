import aiohttp
import asyncio
import urllib.parse
import os
import json
import re
import difflib

class ModelSearcher:
    def __init__(self):
        self.civitai_api = "https://civitai.com/api/v1/models"
        self.hf_api = "https://huggingface.co/api/models"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()
        
        # 常见后缀词（搜索时应移除以提高精度）
        self.NOISE_SUFFIXES = {
            'fp16', 'fp32', 'bf16', 'int8', 'int4',
            'pruned', 'ema', 'emaonly', 'noembed',
            'safetensors', 'ckpt', 'pt', 'bin', 'pth',
            'inpainting', 'vae', 'unet', 'lora',
            'fix', 'fixed', 'final', 'official',
            'sfw', 'nsfw', 'base', 'refiner'
        }
        
        # 常见模型名缩写映射（帮助搜索标准化）
        self.MODEL_ALIASES = {
            'sdxl': 'stable diffusion xl',
            'sd15': 'stable diffusion 1.5',
            'sd': 'stable diffusion',
            'flux': 'flux',
            'realvis': 'realvisxl',
            'jugg': 'juggernaut',
        }

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AutoModelMatcher] Failed to load config: {e}")
        return {"civitai_api_key": ""}

    def save_config(self, new_config):
        self.config.update(new_config)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[AutoModelMatcher] Failed to save config: {e}")

    def get_config(self):
        return self.config

    def _get_headers(self, api_key=None, for_site="civitai"):
        """
        生成伪装成真实浏览器的请求头
        使用多种 User-Agent 随机轮换，模拟真实浏览器行为
        """
        import random
        
        # 多个真实浏览器 User-Agent 轮换（降低被识别风险）
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        
        selected_ua = random.choice(user_agents)
        
        # 完整的浏览器指纹头
        headers = {
            "User-Agent": selected_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors", 
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }
        
        # 根据目标站点设置 Referer 和 Origin
        if for_site == "civitai":
            headers["Referer"] = "https://civitai.com/models"
            headers["Origin"] = "https://civitai.com"
        elif for_site == "huggingface":
            headers["Referer"] = "https://huggingface.co/models"
            headers["Origin"] = "https://huggingface.co"
        
        # 优先使用传入的临时 key (用于验证)，否则使用配置存储的 key
        token = api_key if api_key else self.config.get("civitai_api_key")
        if token and token.strip():
            headers["Authorization"] = f"Bearer {token.strip()}"
            
        return headers

    # ========== 核心优化: 智能搜索词提取 ==========
    
    def _extract_search_terms(self, filename):
        """
        从文件名中提取多个候选搜索词（从精确到宽松）
        
        例如: "realvisxl_v3.0_turbo_fp16.safetensors"
        返回: ["realvisxl v3.0 turbo", "realvisxl v3", "realvisxl"]
        
        :param filename: 模型文件名 (可含路径)
        :return: List[str] 候选搜索词列表
        """
        # 1. 提取纯文件名（无路径无后缀）
        name_only = os.path.basename(filename)
        base_name, _ = os.path.splitext(name_only)
        
        # 2. 转小写，将分隔符统一为空格
        normalized = base_name.lower()
        for char in ['_', '-', '.', '+']:
            normalized = normalized.replace(char, ' ')
        
        # 3. 拆分为 token 列表
        tokens = normalized.split()
        
        # 4. 过滤噪声后缀词
        clean_tokens = [t for t in tokens if t not in self.NOISE_SUFFIXES]
        
        # 5. 识别版本号 (例如 v1, v3.0, 1.0, etc)
        version_pattern = re.compile(r'^v?\d+(\.\d+)?$')
        version_tokens = [t for t in clean_tokens if version_pattern.match(t)]
        core_tokens = [t for t in clean_tokens if not version_pattern.match(t)]
        
        # 6. 生成多级搜索词（降级策略）
        search_terms = []
        
        # Level 1: 核心词 + 版本号（最精确）
        if core_tokens and version_tokens:
            search_terms.append(' '.join(core_tokens + version_tokens[:1]))
        
        # Level 2: 仅核心词
        if core_tokens:
            search_terms.append(' '.join(core_tokens))
        
        # Level 3: 首个核心词（最后兜底）
        if core_tokens and len(core_tokens) > 1:
            search_terms.append(core_tokens[0])
        
        # 去重并保留顺序
        seen = set()
        unique_terms = []
        for term in search_terms:
            if term and term not in seen:
                seen.add(term)
                unique_terms.append(term)
        
        # 如果无法提取任何有效词，返回原始 base_name
        if not unique_terms:
            unique_terms = [base_name.replace('_', ' ').replace('-', ' ').strip()]
        
        return unique_terms

    def _tokenize(self, text):
        """将文本拆分为 token 集合"""
        text = text.lower()
        for char in ['_', '-', '.', ' ']:
            text = text.replace(char, ' ')
        return set(t.strip() for t in text.split() if t.strip())
    
    def _calculate_similarity(self, name_a, name_b):
        """
        计算两个名称的综合相似度 (0-1)
        结合 Token Overlap (Jaccard) 和 Sequence Similarity (difflib)
        """
        if not name_a or not name_b:
            return 0.0
        
        name_a = name_a.lower()
        name_b = name_b.lower()
        
        # 1. Token 相似度 (Jaccard)
        tokens_a = self._tokenize(name_a)
        tokens_b = self._tokenize(name_b)
        
        if not tokens_a or not tokens_b:
            return 0.0
        
        intersection = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        jaccard = intersection / union if union > 0 else 0.0
        
        # 2. 序列相似度 (difflib SequenceMatcher)
        seq_ratio = difflib.SequenceMatcher(None, name_a, name_b).ratio()
        
        # 3. 综合评分 (加权平均，Token 更重要)
        combined = jaccard * 0.6 + seq_ratio * 0.4
        
        return combined

    # ========== API 验证 ==========
    
    async def validate_api_key(self, api_key):
        """
        验证 API Key 是否有效
        :param api_key: 用户输入的 API Key
        :return: (bool, str) -> (is_valid, message)
        """
        if not api_key or not api_key.strip():
            return False, "API Key is empty"
            
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = self._get_headers(api_key)
            url = f"{self.civitai_api}?limit=1"
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return True, "Valid API Key"
                    elif response.status == 401:
                        return False, "Invalid API Key (401 Unauthorized)"
                    elif response.status == 403:
                        text = await response.text()
                        if "Just a moment" in text or "Challenge" in text:
                            return False, "403 Blocked by Cloudflare WAF (Try updating User-Agent or IP)"
                        return False, "403 Forbidden (API Key accepted but access denied)"
                    else:
                        return False, f"Unexpected status: {response.status}"
        except Exception as e:
            return False, str(e)

    # ========== 主搜索入口 ==========
    
    async def search(self, filename):
        """
        搜索模型下载链接
        :param filename: 模型文件名 (e.g. "v1-5-pruned.ckpt")
        :return: {"url": "...", "source": "Civitai/HuggingFace", "name": "...", "pageUrl": "..."} or None
        """
        # 1. 提取候选搜索词
        search_terms = self._extract_search_terms(filename)
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        print(f"[AutoModelMatcher] 正在搜索: {filename}")
        print(f"[AutoModelMatcher] 候选搜索词: {search_terms}")
        
        # 2. 并发搜索 Civitai 和 HuggingFace
        tasks = [
            self._search_civitai_multi(search_terms, base_name),
            self._search_hf_multi(search_terms, base_name),
        ]
        
        results = await asyncio.gather(*tasks)
        civitai_res, hf_res = results
        
        # 3. 优先级策略: Civitai > HuggingFace
        if civitai_res:
            print(f"[AutoModelMatcher] ✓ Civitai 命中: {civitai_res.get('name')}")
            return civitai_res
        if hf_res:
            print(f"[AutoModelMatcher] ✓ HuggingFace 命中: {hf_res.get('name')}")
            return hf_res
        
        print(f"[AutoModelMatcher] ✗ 未找到匹配: {filename}")
        return None

    # ========== Civitai 搜索 (优化版) ==========
    
    async def _search_civitai_multi(self, search_terms, original_base_name):
        """
        使用多个搜索词依次尝试 Civitai 搜索
        返回第一个高置信度匹配
        """
        for term in search_terms:
            result = await self._search_civitai_single(term, original_base_name)
            if result:
                return result
        return None
    
    async def _search_civitai_single(self, query_term, original_base_name):
        """
        单次 Civitai API 搜索，使用相似度评分筛选结果
        """
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers()
            query = urllib.parse.quote(query_term)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                url = f"{self.civitai_api}?query={query}&limit=5"  # 增加结果数量
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    items = data.get("items", [])
                    if not items:
                        return None
                    
                    original_lower = original_base_name.lower()
                    best_match = None
                    best_score = 0.0
                    
                    # 遍历所有搜索结果，计算相似度评分
                    for item in items:
                        model_id = item.get("id")
                        model_name = item.get("name", "")
                        
                        for version in item.get("modelVersions", []):
                            version_id = version.get("id")
                            version_name = version.get("name", "")
                            
                            for file_info in version.get("files", []):
                                fname = file_info.get("name", "")
                                fname_base = os.path.splitext(fname)[0].lower()
                                
                                # 计算文件名相似度
                                file_score = self._calculate_similarity(original_lower, fname_base)
                                
                                # 计算模型名相似度（作为补充）
                                model_score = self._calculate_similarity(original_lower, model_name.lower())
                                
                                # 综合评分（文件名权重更高）
                                combined_score = file_score * 0.7 + model_score * 0.3
                                
                                if combined_score > best_score:
                                    best_score = combined_score
                                    best_match = {
                                        "url": file_info.get("downloadUrl"),
                                        "source": "Civitai",
                                        "name": f"{model_name} - {version_name}",
                                        "pageUrl": f"https://civitai.com/models/{model_id}?modelVersionId={version_id}",
                                        "score": combined_score
                                    }
                    
                    # 只返回评分高于阈值的匹配 (阈值 0.35)
                    if best_match and best_score >= 0.35:
                        return best_match
                    
        except Exception as e:
            print(f"[AutoModelMatcher] Civitai 搜索错误: {e}")
        
        return None

    # ========== HuggingFace 搜索 (优化版) ==========
    
    async def _search_hf_multi(self, search_terms, original_base_name):
        """
        使用多个搜索词依次尝试 HuggingFace 搜索
        """
        for term in search_terms:
            result = await self._search_hf_single(term, original_base_name)
            if result:
                return result
        return None
    
    async def _search_hf_single(self, query_term, original_base_name):
        """
        单次 HuggingFace API 搜索，使用相似度评分筛选结果
        """
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers(for_site="huggingface")
            query = urllib.parse.quote(query_term)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                url = f"{self.hf_api}?search={query}&limit=5"
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    if not data:
                        return None
                    
                    original_lower = original_base_name.lower()
                    best_match = None
                    best_score = 0.0
                    
                    for repo in data:
                        model_id = repo.get("modelId", "")  # e.g. "stabilityai/sd-vae-ft-mse"
                        repo_name = model_id.split("/")[-1] if "/" in model_id else model_id
                        
                        # 计算相似度
                        score = self._calculate_similarity(original_lower, repo_name.lower())
                        
                        if score > best_score:
                            best_score = score
                            best_match = {
                                "url": f"https://huggingface.co/{model_id}/tree/main",
                                "source": "HuggingFace",
                                "name": model_id,
                                "pageUrl": f"https://huggingface.co/{model_id}",
                                "score": score
                            }
                    
                    # 只返回评分高于阈值的匹配 (阈值 0.30)
                    if best_match and best_score >= 0.30:
                        return best_match
                    
        except Exception as e:
            print(f"[AutoModelMatcher] HuggingFace 搜索错误: {e}")
        
        return None
