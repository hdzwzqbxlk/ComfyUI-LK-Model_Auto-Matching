import aiohttp
import asyncio
import urllib.parse
import os
import json
import difflib
import re
try:
    from .utils import AdvancedTokenizer
except ImportError:
    from utils import AdvancedTokenizer

class ModelSearcher:
    def __init__(self):
        self.civitai_api = "https://civitai.com/api/v1/models"
        self.hf_api = "https://huggingface.co/api/models"
        self.modelscope_api = "https://www.modelscope.cn/api/v1/dolphin/models"
        # 配置文件路径 (保存在项目根目录，即 core 的上级目录)
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        self.config = self.load_config()
        
        # 搜索结果缓存 {search_term: result}
        self.search_cache = {}

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
        import random
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        selected_ua = random.choice(user_agents)
        headers = {
            "User-Agent": selected_ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
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
            headers["X-Requested-With"] = "XMLHttpRequest"
        
        token = api_key if api_key else self.config.get("civitai_api_key")
        if token and token.strip() and for_site == "civitai":
            headers["Authorization"] = f"Bearer {token.strip()}"
            
        return headers

    async def validate_api_key(self, api_key):
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
                            return False, "403 Blocked by Cloudflare WAF"
                        return False, "403 Forbidden"
                    else:
                        return False, f"Unexpected status: {response.status}"
        except Exception as e:
            return False, str(e)

    async def search(self, filename, ignore_cache=False):
        """
        搜索模型下载链接 (带缓存)
        """
        if not filename: return None
        
        # 0. 检查缓存
        if not ignore_cache and filename in self.search_cache:
            print(f"[AutoModelMatcher] Cache Hit: {filename}")
            return self.search_cache[filename]

        # 0.5 主流模型快速匹配 (ComfyUI 官方模型直接返回 HF 链接)
        repo_id, matched_key = AdvancedTokenizer.lookup_popular_model(filename)
        if repo_id:
            print(f"[AutoModelMatcher] ⚡ 主流模型快速匹配: {matched_key} -> {repo_id}")
            result = {
                "url": f"https://huggingface.co/{repo_id}/tree/main",
                "source": "HuggingFace (ComfyUI官方)",
                "name": repo_id,
                "pageUrl": f"https://huggingface.co/{repo_id}",
                "score": 1.0  # 精确匹配满分
            }
            self.search_cache[filename] = result
            return result

        # 1. 提取候选搜索词
        # 使用统一的 AdvancedTokenizer
        search_terms = AdvancedTokenizer.extract_search_terms(filename)
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        print(f"[AutoModelMatcher] 正在搜索: {filename}")
        print(f"[AutoModelMatcher] 候选搜索词: {search_terms}")
        
        # 2. 并发搜索三个平台
        tasks = [
            self._search_civitai_multi(search_terms, base_name),
            self._search_hf_multi(search_terms, base_name),
            self._search_modelscope_multi(search_terms, base_name),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        civitai_res = results[0] if not isinstance(results[0], Exception) else None
        hf_res = results[1] if not isinstance(results[1], Exception) else None
        modelscope_res = results[2] if not isinstance(results[2], Exception) else None
        
        final_result = None
        
        # 3. 优先级策略
        if civitai_res:
            print(f"[AutoModelMatcher] ✓ Civitai 命中: {civitai_res.get('name')}")
            final_result = civitai_res
        elif hf_res:
            print(f"[AutoModelMatcher] ✓ HuggingFace 命中: {hf_res.get('name')}")
            final_result = hf_res
        elif modelscope_res:
            print(f"[AutoModelMatcher] ✓ ModelScope 命中: {modelscope_res.get('name')}")
            final_result = modelscope_res
        else:
            # 4. Google 终极兜底 (如果前面都失败)
            print(f"[AutoModelMatcher] 尝试 Google 终极搜索...")
            # 只用第一个最有希望的搜索词
            google_res = await self._search_google_html(search_terms[0], base_name)
            if google_res:
                print(f"[AutoModelMatcher] ✓ Google Search 命中: {google_res.get('name')}")
                final_result = google_res
            else:
                print(f"[AutoModelMatcher] ✗ 未找到匹配: {filename}")
        
        # 写入缓存 (即使是 None 也缓存，避免重复无效搜索)
        self.search_cache[filename] = final_result
        return final_result

    async def _search_modelscope_multi(self, search_terms, original_base_name):
        for term in search_terms:
            result = await self._search_modelscope_single(term, original_base_name)
            if result:
                # 高置信度早停：避免尝试后续搜索词
                if result.get("score", 0) > 0.7:
                    return result
                return result
        return None
    
    async def _search_modelscope_single(self, query_term, original_base_name):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers(for_site="modelscope")
            headers["Accept"] = "application/json, text/plain, */*"
            headers["Content-Type"] = "application/json"
            api_url = "https://modelscope.cn/api/v1/dolphin/models"
            request_body = {
                "PageSize": 24, "PageNumber": 1, "SearchText": query_term, "Sort": {"SortBy": "Default"}
            }
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.put(api_url, headers=headers, json=request_body) as response:
                    if response.status != 200: return None
                    data = await response.json()
                    if not data.get("Success", False): return None
                    models = data.get("Data", {}).get("Model", {}).get("Models", [])
                    if not models: return None
                    
                    best_match = None
                    best_score = 0.0
                    original_lower = original_base_name.lower()
                    
                    for model in models[:15]:
                        org_name = model.get("Path", "")
                        model_name = model.get("Name", "")
                        chinese_name = model.get("ChineseName", "")
                        if not org_name or not model_name: continue
                        
                        full_path = f"{org_name}/{model_name}"
                        scores = [
                            AdvancedTokenizer.calculate_similarity(original_lower, model_name.lower()),
                            AdvancedTokenizer.calculate_similarity(original_lower, full_path.lower().replace("/", " ")),
                        ]
                        if chinese_name:
                            scores.append(AdvancedTokenizer.calculate_similarity(original_lower, chinese_name.lower()))
                        
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
                    
                    # 提高阈值到 0.35，减少误匹配
                    if best_match and best_score >= 0.35:
                        return best_match
        except Exception:
            pass
        return None

    async def _search_civitai_multi(self, search_terms, original_base_name):
        for term in search_terms:
            result = await self._search_civitai_single(term, original_base_name)
            if result:
                # 高置信度早停
                if result.get("score", 0) > 0.7:
                    return result
                return result
        return None
    
    async def _search_civitai_single(self, query_term, original_base_name):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers(for_site="civitai")
            query = urllib.parse.quote(query_term)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                url = f"{self.civitai_api}?query={query}&limit=10"
                async with session.get(url) as response:
                    if response.status != 200: return None
                    data = await response.json()
                    items = data.get("items", [])
                    if not items: return None
                    
                    original_lower = original_base_name.lower()
                    best_match = None
                    best_score = 0.0
                    
                    for item in items:
                        model_id = item.get("id")
                        model_name = item.get("name", "")
                        for version in item.get("modelVersions", []):
                            version_id = version.get("id")
                            version_name = version.get("name", "")
                            for file_info in version.get("files", []):
                                fname = file_info.get("name", "")
                                fname_base = os.path.splitext(fname)[0].lower()
                                
                                file_score = AdvancedTokenizer.calculate_similarity(original_lower, fname_base)
                                full_name = f"{model_name} {version_name}".lower()
                                model_score = AdvancedTokenizer.calculate_similarity(original_lower, full_name)
                                
                                # [Strict Check] If file score is strictly 0 (mismatch), discard even if model matches
                                if file_score < 0.05: continue
                                
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
                    # 提高阈值到 0.40，减少误匹配
                    if best_match and best_score >= 0.40:
                        return best_match
        except Exception as e:
            print(f"[AutoModelMatcher] Civitai 搜索错误: {e}")
        return None

    async def _search_hf_multi(self, search_terms, original_base_name):
        for term in search_terms:
            result = await self._search_hf_single(term, original_base_name)
            if result:
                # 高置信度早停
                if result.get("score", 0) > 0.7:
                    return result
                return result
        return None
    
    async def _search_hf_single(self, query_term, original_base_name):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            headers = self._get_headers(for_site="huggingface")
            query = urllib.parse.quote(query_term)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                url = f"{self.hf_api}?search={query}&limit=10"
                async with session.get(url) as response:
                    if response.status != 200: return None
                    data = await response.json()
                    if not data: return None
                    
                    original_lower = original_base_name.lower()
                    best_match = None
                    best_score = 0.0
                    
                    for repo in data:
                        model_id = repo.get("modelId", "")
                        repo_name = model_id.split("/")[-1] if "/" in model_id else model_id
                        
                        score = AdvancedTokenizer.calculate_similarity(original_lower, repo_name.lower())
                        full_score = AdvancedTokenizer.calculate_similarity(original_lower, model_id.lower().replace("/", " "))
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
                    # 提高阈值到 0.35，减少误匹配
                    if best_match and best_score >= 0.35:
                        return best_match
        except Exception as e:
            print(f"[AutoModelMatcher] HuggingFace 搜索错误: {e}")
        return None
    async def _fetch_civitai_meta(self, model_id):
        """根据 ID 获取 Civitai 模型元数据"""
        try:
            url = f"https://civitai.com/api/v1/models/{model_id}"
            timeout = aiohttp.ClientTimeout(total=5)
            # headers = self._get_headers(for_site="civitai") # Optional
            async with aiohttp.ClientSession(timeout=timeout) as session:
                 async with session.get(url) as response:
                     if response.status == 200:
                         data = await response.json()
                         if "modelVersions" in data and data["modelVersions"]:
                             latest = data["modelVersions"][0]
                             files = latest.get("files", [])
                             if files:
                                 return {
                                     "url": files[0].get("downloadUrl"),
                                     "source": "Civitai (Google)",
                                     "name": f"{data.get('name')} - {latest.get('name')}",
                                     "pageUrl": f"https://civitai.com/models/{model_id}",
                                     "score": 0 # 待计算
                                 }
        except:
            pass
        return None


        return None

    async def _deep_scrape_page(self, url, target_filename):
        """深入抓取网页，寻找匹配的下载直链"""
        try:
            print(f"[AutoModelMatcher] 正在挖掘页面直链: {url}")
            timeout = aiohttp.ClientTimeout(total=10)
            headers = self._get_headers() # generic
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200: return None
                    html = await response.text()
                    
                    # 提取所有 .safetensors, .gguf, .ckpt 链接
                    # href="..."
                    links = re.findall(r'href=["\'](https?://[^"\']+\.(?:safetensors|gguf|ckpt|pt|pth))["\']', html)
                    
                    best_link = None
                    best_score = 0.0
                    target_base = os.path.splitext(target_filename)[0].lower()
                    
                    for link in links:
                        # link is download url
                        fname = link.split("/")[-1]
                        fname = urllib.parse.unquote(fname)
                        fname_base = os.path.splitext(fname)[0].lower()
                        
                        # Calculate Similarity
                        score = AdvancedTokenizer.calculate_similarity(target_base, fname_base)
                        
                        # Strict Quantization Check inside scraping too
                        quant_target = AdvancedTokenizer.detect_quantization(target_filename)
                        quant_cand = AdvancedTokenizer.detect_quantization(fname)
                        if quant_target and quant_cand and quant_target != quant_cand:
                            # Strict mismatch
                            continue
                            
                        if score > best_score:
                            best_score = score
                            best_link = link
                            
                    if best_link and best_score > 0.4: # slightly higher threshold for validation
                        return {
                            "url": best_link,
                            "source": "Doc/GitHub (Scraped)",
                            "name": os.path.basename(best_link),
                            "pageUrl": url,
                            "score": best_score
                        }
        except Exception as e:
            print(f"[AutoModelMatcher] Deep scrape failed: {e}")
        return None

    async def _search_google_html(self, query, original_base_name):
        """
        使用 Google 搜索 (HTML Scraper) 作为最后的兜底
        技巧: site:modelscope.cn OR site:civitai.com ... 进行精准目标搜索
        """
        try:
            # 构建高级搜索指令
            # Expanded to include Documentation sites
            sites = "site:modelscope.cn OR site:civitai.com OR site:huggingface.co OR site:docs.comfy.org OR site:github.com"
            search_query = urllib.parse.quote(f"{query} {sites}")
            
            # 使用 google.com 
            url = f"https://www.google.com/search?q={search_query}&num=10&hl=en"
            
            headers = self._get_headers(for_site="google")
            headers["Host"] = "www.google.com"
            headers["Referer"] = "https://www.google.com/"
            
            print(f"[AutoModelMatcher] 尝试 Google 定向搜索: {query} (in ModelScope/Civitai/HF/Docs)")
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None
                    
                    html = await response.text()
                    
                    # 预处理：提取 Google 跳转链接并解码
                    # Google 链接通常是 /url?q=https%3A%2F%2F...&sa=...
                    decoded_urls = []
                    # Relaxed regex to capture encoded 'https%3A...'
                    google_redirects = re.findall(r'url\?q=([^"&]+)', html)
                    for raw_link in google_redirects:
                        try:
                            decoded = urllib.parse.unquote(raw_link)
                            if decoded.startswith("http"):
                                decoded_urls.append(decoded)
                        except:
                            pass
                    
                    # 将解码后的 URL 拼接到原始 HTML 中以便统一正则匹配
                    # (简单粗暴但有效，无需重写下面的所有正则)
                    search_content = html + "\n" + "\n".join(decoded_urls)
                    
                    # 简单 Regex 提取链接
                    results = []
                    
                    # 1. Model Sites (Existing)
                    ms_matches = re.findall(r'modelscope\.cn/models/([^/]+/[^/&?"]+)', search_content)
                    for ms_id in ms_matches: results.append(("modelscope", ms_id))

                    civitai_matches = re.findall(r'civitai\.com/models/(\d+)', search_content)
                    for model_id in civitai_matches: results.append(("civitai", model_id))
                        
                    hf_matches = re.findall(r'huggingface\.co/([^/]+/[^/&?"]+)', search_content)
                    for repo_id in hf_matches:
                        if "tree/main" not in repo_id and "blob/main" not in repo_id:
                             results.append(("hf", repo_id))
                             
                    # 2. Documentation Sites (New)
                    # Extract full URLs for docs
                    doc_matches = re.findall(r'(https://docs\.comfy\.org/[^"&?\s]+)', search_content)
                    for doc_url in doc_matches: results.append(("doc", doc_url))
                    
                    gh_matches = re.findall(r'(https://github\.com/[^/]+/[^/]+)', search_content)
                    for gh_url in gh_matches: results.append(("doc", gh_url))
                             
                    results = list(set(results))
                    
                    if not results:
                        return None
                        
                    print(f"[AutoModelMatcher] Google 发现潜在链接: {len(results)} 个")
                    
                    # 验证并获取元数据 (Limit 5)
                    for platform, pid in results[:5]:
                        meta = None
                        if platform == "civitai":
                             meta = await self._fetch_civitai_meta(pid)
                        elif platform == "hf":
                             meta = {
                                 "url": f"https://huggingface.co/{pid}/tree/main",
                                 "source": "HuggingFace (Google)",
                                 "name": pid,
                                 "pageUrl": f"https://huggingface.co/{pid}",
                             }
                        elif platform == "modelscope":
                             meta = {
                                 "url": f"https://modelscope.cn/models/{pid}/files",
                                 "source": "ModelScope (Google)",
                                 "name": pid,
                                 "pageUrl": f"https://modelscope.cn/models/{pid}",
                             }
                        elif platform == "doc":
                            # Deep Scrape
                            meta = await self._deep_scrape_page(pid, original_base_name + ".safetensors") # Hacky extension?
                             
                        if meta:
                            # Re-verify score
                            score = AdvancedTokenizer.calculate_similarity(original_base_name, meta["name"])
                            meta["score"] = score
                            # 提高阈值到 0.35
                            if score > 0.35: 
                                return meta
        except Exception as e:
            pass
        return None
