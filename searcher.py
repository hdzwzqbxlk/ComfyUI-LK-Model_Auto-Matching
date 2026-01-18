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
        # ModelScope 搜索 API (通过网页搜索接口)
        self.modelscope_api = "https://www.modelscope.cn/api/v1/dolphin/models"
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.config = self.load_config()
        
        # 噪声后缀词（仅过滤纯技术后缀，不过滤版本号和模型组件名）
        self.NOISE_SUFFIXES = {
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
        self.PROTECTED_TERMS = {
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
        self.MODEL_PATTERNS = {
            # (匹配模式, 替代搜索词)
            r'v1[\-_\.]?5': 'stable diffusion 1.5',
            r'v2[\-_\.]?1': 'stable diffusion 2.1',
            r'sd[\-_]?xl': 'stable diffusion xl',
            r'sd[\-_]?3': 'stable diffusion 3',
            r'flux[\-_\.]?1': 'flux.1',
        }
        
        # 常见模型名缩写映射（帮助搜索标准化）
        self.MODEL_ALIASES = {
            'sdxl': 'stable diffusion xl',
            'sd15': 'stable diffusion 1.5',
            'sd21': 'stable diffusion 2.1',
            'sd': 'stable diffusion',
            'flux': 'flux',
            'realvis': 'realvisxl',
            'jugg': 'juggernaut',
            'qwen': 'qwen',
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
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        
        # 根据目标站点设置 Referer 和 Origin
        if for_site == "civitai":
            headers["Referer"] = "https://civitai.com/models"
            headers["Origin"] = "https://civitai.com"
            headers["Sec-Fetch-Dest"] = "empty"
            headers["Sec-Fetch-Mode"] = "cors"
            headers["Sec-Fetch-Site"] = "same-origin"
            headers["Sec-Ch-Ua"] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            headers["Sec-Ch-Ua-Mobile"] = "?0"
            headers["Sec-Ch-Ua-Platform"] = '"Windows"'
        elif for_site == "huggingface":
            headers["Referer"] = "https://huggingface.co/models"
            headers["Origin"] = "https://huggingface.co"
        elif for_site == "modelscope":
            headers["Referer"] = "https://www.modelscope.cn/models"
            headers["Origin"] = "https://www.modelscope.cn"
            # ModelScope 需要额外的请求头
            headers["X-Requested-With"] = "XMLHttpRequest"
        
        # 优先使用传入的临时 key (用于验证)，否则使用配置存储的 key
        token = api_key if api_key else self.config.get("civitai_api_key")
        if token and token.strip() and for_site == "civitai":
            headers["Authorization"] = f"Bearer {token.strip()}"
            
        return headers

    # ========== 核心优化: 智能搜索词提取 ==========
    
    def _extract_search_terms(self, filename):
        """
        从文件名中提取多个候选搜索词（智能提取算法）
        
        策略:
        1. 预处理: 统一分隔符，转小写
        2. 模式识别: 识别常见模型族 (如 "v1-5" -> "stable diffusion 1.5")
        3. 分词清洗: 过滤噪声，但保留保护词
        4. 多级生成: 生成从精确到宽泛的搜索词组合
        """
        # 1. 提取纯文件名
        name_only = os.path.basename(filename)
        base_name, _ = os.path.splitext(name_only)
        normalized_name = base_name.lower()
        
        # 2. 检查模型模式 (Pattern Matching)
        # 如果文件名包含特定模式（如 v1-5），直接添加对应的标准全名作为首选搜索词
        pattern_matches = []
        for pattern_str, replacement in self.MODEL_PATTERNS.items():
            if re.search(pattern_str, normalized_name):
                pattern_matches.append(replacement)
        
        # 3. 分词与清洗
        # 替换所有分隔符为空格
        cleaned_text = normalized_name
        for char in ['_', '-', '.', '+', '\\', '/', '[', ']', '(', ')']:
            cleaned_text = cleaned_text.replace(char, ' ')
        
        raw_tokens = [t.strip() for t in cleaned_text.split() if t.strip()]
        
        # 过滤逻辑
        final_tokens = []
        for t in raw_tokens:
            # 规则 A: 如果是保护词，永远保留
            if t in self.PROTECTED_TERMS:
                final_tokens.append(t)
                continue
            
            # 规则 B: 如果是噪声词，过滤
            if t in self.NOISE_SUFFIXES:
                continue
                
            # 规则 C: 纯版本号处理 (v1.0, 1.0)
            # 如果前面已经是保护词(如 sd 1.5)，数字保留意义大；否则可能是噪声
            # 这里简单起见，如果不是纯数字或纯版本格式，保留
            # 或者如果它是保护词的一部分（已在规则A处理）
            
            # 过滤纯版本号/日期/哈希 (简单启发式: 纯数字或 v+数字)
            if re.match(r'^v?\d+(\.\d+)*$', t):
                 # 如果是单独的数字，且不在保护列表，可能在组合词中才有意义
                 # 暂且保留，依赖组合逻辑
                 final_tokens.append(t)
            else:
                final_tokens.append(t)
        
        # 4. 生成搜索词
        search_terms = []
        
        # 优先级 0: 模式匹配结果 (如 "stable diffusion 1.5")
        search_terms.extend(pattern_matches)
        
        # 优先级 1: 所有保留 Token 组合
        if final_tokens:
            search_terms.append(" ".join(final_tokens))
        
        # 优先级 2: 核心词识别 (Known Families)
        # 尝试提取已知的模型族名称 (sdxl, flux, qwen 等) 并构建 "族 + 剩余强特征"
        known_families = [t for t in final_tokens if t in self.MODEL_ALIASES or t in {'flux', 'sd', 'sdxl', 'qwen', 'llama'}]
        if known_families:
            # 如果识别出核心族，尝试构建 "Family + Next Token"
            # 例如 "flux 1 dev"
            # 取前 3 个 token
            if len(final_tokens) > 1:
                 search_terms.append(" ".join(final_tokens[:3]))
        
        # 优先级 3: 宽松组合 (前2-3个词)
        if len(final_tokens) > 3:
            search_terms.append(" ".join(final_tokens[:3]))
        if len(final_tokens) > 2:
            search_terms.append(" ".join(final_tokens[:2]))
            
        # 优先级 4: 单一核心词 (如果列表很短)
        if len(final_tokens) == 1:
            # 已经加过了(优先级1)，不用重复
            pass
        elif final_tokens:
             # 取第一个词作为兜底 (如 "flux")
             search_terms.append(final_tokens[0])

        # 5. 去重与标准化
        unique_terms = []
        seen = set()
        
        for term in search_terms:
            t = term.strip()
            if not t: continue
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        
        # 兜底: 如果什么都没提取出来，使用原始文件名(去分隔符)
        if not unique_terms:
            fallback = cleaned_text.strip()
            if fallback:
                unique_terms.append(fallback)
            else:
                unique_terms.append(base_name) # 极其罕见
                
        return unique_terms

    def _tokenize(self, text):
        """将文本拆分为 token 集合 (支持数字分离: flux1 -> flux 1)"""
        text = text.lower()
        # 替换常见分隔符
        for char in ['_', '-', '.', ' ', '/', '\\']:
            text = text.replace(char, ' ')
        
        # 使用正则切分数字，使得 "flux1" -> "flux", "1"
        # 这样 "flux1" 和 "flux.1" 就会有相同的 token 集合
        tokens = []
        for part in text.split():
            # split alpha and numeric
            sub_tokens = re.findall(r'[a-z]+|\d+', part)
            if sub_tokens:
                tokens.extend(sub_tokens)
            else:
                tokens.append(part)
                
        return set(t.strip() for t in tokens if t.strip() and len(t.strip()) >= 1)
    
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
        
        # 3. 核心词包含检查（加分项）
        # 如果 A 的核心词完全包含在 B 中，或反之，给予额外加分
        core_bonus = 0.0
        if tokens_a.issubset(tokens_b) or tokens_b.issubset(tokens_a):
            core_bonus = 0.15
        
        # 4. 综合评分 (加权平均)
        combined = jaccard * 0.5 + seq_ratio * 0.35 + core_bonus
        
        return min(combined, 1.0)

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
        :return: {"url": "...", "source": "Civitai/HuggingFace/ModelScope", "name": "...", "pageUrl": "..."} or None
        """
        # 1. 提取候选搜索词
        search_terms = self._extract_search_terms(filename)
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        print(f"[AutoModelMatcher] 正在搜索: {filename}")
        print(f"[AutoModelMatcher] 候选搜索词: {search_terms}")
        
        # 2. 并发搜索三个平台: Civitai + HuggingFace + ModelScope
        # 注意: ModelScope API 搜索功能不稳定（可能返回热门推荐而非关键词匹配），作为最后备选
        tasks = [
            self._search_civitai_multi(search_terms, base_name),
            self._search_hf_multi(search_terms, base_name),
            self._search_modelscope_multi(search_terms, base_name),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理可能的异常
        civitai_res = results[0] if not isinstance(results[0], Exception) else None
        hf_res = results[1] if not isinstance(results[1], Exception) else None
        modelscope_res = results[2] if not isinstance(results[2], Exception) else None
        
        # 3. 优先级策略: Civitai(模型全) > HuggingFace > ModelScope(备选)
        if civitai_res:
            print(f"[AutoModelMatcher] ✓ Civitai 命中: {civitai_res.get('name')}")
            return civitai_res
        if hf_res:
            print(f"[AutoModelMatcher] ✓ HuggingFace 命中: {hf_res.get('name')}")
            return hf_res
        if modelscope_res:
            print(f"[AutoModelMatcher] ✓ ModelScope 命中: {modelscope_res.get('name')}")
            return modelscope_res
        
        print(f"[AutoModelMatcher] ✗ 未找到匹配: {filename}")
        return None

    # ========== ModelScope 搜索 (新增) ==========
    
    async def _search_modelscope_multi(self, search_terms, original_base_name):
        """
        使用多个搜索词依次尝试 ModelScope 搜索
        返回第一个高置信度匹配
        """
        for term in search_terms:
            result = await self._search_modelscope_single(term, original_base_name)
            if result:
                return result
        return None
    
    async def _search_modelscope_single(self, query_term, original_base_name):
        """
        单次 ModelScope 搜索 - 使用 PUT API 方式
        
        魔搭社区 API 端点: https://modelscope.cn/api/v1/dolphin/models
        方法: PUT (非标准但有效)
        请求体: {"PageSize": 24, "PageNumber": 1, "SearchText": "xxx", "Sort": {"SortBy": "Default"}}
        
        响应格式:
        {
            "Code": 200,
            "Success": true,
            "Data": {
                "Model": {
                    "Models": [
                        {"Name": "model-id", "ChineseName": "显示名称", "Path": "Owner/Repo"}
                    ],
                    "TotalCount": 100
                }
            }
        }
        
        下载直链: https://modelscope.cn/models/{path}/resolve/master/{file}
        """
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers(for_site="modelscope")
            # 使用 JSON 请求头
            headers["Accept"] = "application/json, text/plain, */*"
            headers["Content-Type"] = "application/json"
            
            # 魔搭模型搜索 API
            api_url = "https://modelscope.cn/api/v1/dolphin/models"
            
            # PUT 请求体
            request_body = {
                "PageSize": 24,
                "PageNumber": 1,
                "SearchText": query_term,
                "Sort": {"SortBy": "Default"}
            }
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(api_url, headers=headers, json=request_body) as response:
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    # 检查 API 响应是否成功
                    if not data.get("Success", False):
                        return None
                    
                    # 提取模型列表
                    model_data = data.get("Data", {}).get("Model", {})
                    models = model_data.get("Models", [])
                    
                    if not models:
                        return None
                    
                    # 计算相似度，找到最佳匹配
                    original_lower = original_base_name.lower()
                    best_match = None
                    best_score = 0.0
                    
                    for model in models[:15]:  # 只检查前15个结果
                        # 提取模型信息
                        # 注意: API 返回的 Path 是组织名，Name 是模型名
                        org_name = model.get("Path", "")  # 组织名，如 "Lightricks"
                        model_name = model.get("Name", "")  # 模型名，如 "LTX-2"
                        chinese_name = model.get("ChineseName", "")  # 中文名
                        
                        if not org_name or not model_name:
                            continue
                        
                        # 构建完整路径: org/model
                        full_path = f"{org_name}/{model_name}"
                        
                        # 多维度计算相似度
                        scores = [
                            self._calculate_similarity(original_lower, model_name.lower()),
                            self._calculate_similarity(original_lower, full_path.lower().replace("/", " ")),
                        ]
                        # 中文名也参与匹配（如果有）
                        if chinese_name:
                            scores.append(self._calculate_similarity(original_lower, chinese_name.lower()))
                        
                        score = max(scores)
                        
                        if score > best_score:
                            best_score = score
                            page_url = f"https://modelscope.cn/models/{full_path}"
                            best_match = {
                                "url": f"{page_url}/files",
                                "source": "ModelScope",
                                "name": chinese_name if chinese_name else model_name,
                                "pageUrl": page_url,
                                "score": score
                            }
                    
                    # 只返回评分高于阈值的匹配 (阈值 0.25)
                    if best_match and best_score >= 0.25:
                        return best_match
                    
        except Exception as e:
            # 静默处理异常，避免干扰其他搜索源
            # print(f"[AutoModelMatcher] ModelScope 搜索错误: {e}")
            pass
        
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
            headers = self._get_headers(for_site="civitai")
            query = urllib.parse.quote(query_term)
            
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                url = f"{self.civitai_api}?query={query}&limit=10"  # 增加结果数量
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
                                
                                # 计算模型名+版本名相似度（作为补充）
                                full_name = f"{model_name} {version_name}".lower()
                                model_score = self._calculate_similarity(original_lower, full_name)
                                
                                # 综合评分（文件名权重更高）
                                combined_score = file_score * 0.6 + model_score * 0.4
                                
                                if combined_score > best_score:
                                    best_score = combined_score
                                    best_match = {
                                        "url": file_info.get("downloadUrl"),
                                        "source": "Civitai",
                                        "name": f"{model_name} - {version_name}",
                                        "pageUrl": f"https://civitai.com/models/{model_id}?modelVersionId={version_id}",
                                        "score": combined_score
                                    }
                    
                    # 只返回评分高于阈值的匹配 (阈值 0.30)
                    if best_match and best_score >= 0.30:
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
                url = f"{self.hf_api}?search={query}&limit=10"
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
                        
                        # 也尝试和完整 model_id 比较
                        full_score = self._calculate_similarity(original_lower, model_id.lower().replace("/", " "))
                        score = max(score, full_score)
                        
                        if score > best_score:
                            best_score = score
                            best_match = {
                                "url": f"https://huggingface.co/{model_id}/tree/main",
                                "source": "HuggingFace",
                                "name": model_id,
                                "pageUrl": f"https://huggingface.co/{model_id}",
                                "score": score
                            }
                    
                    # 只返回评分高于阈值的匹配 (阈值 0.25)
                    if best_match and best_score >= 0.25:
                        return best_match
                    
        except Exception as e:
            print(f"[AutoModelMatcher] HuggingFace 搜索错误: {e}")
        
        return None
