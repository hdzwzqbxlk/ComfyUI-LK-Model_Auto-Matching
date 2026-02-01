import asyncio
import urllib.parse
import os
import json
import re
import random
import hashlib
from curl_cffi.requests import AsyncSession
from parsel import Selector

try:
    from .utils import AdvancedTokenizer
except ImportError:
    from utils import AdvancedTokenizer

class BaseProvider:
    def __init__(self, config=None):
        self.config = config or {}
        # Update to newer impersonation to avoid blocking
        # curl_cffi supports chrome124 in newer versions, or verify installed version
        self.impersonate = "chrome124"
        self.timeout = 3  # [v3.3.1] 极限优化: 压缩超时

    def _get_headers(self, referer=None):
        # curl_cffi handles User-Agent and TLS natively via 'impersonate'
        # We only need to add specific logic headers if API requires them
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if referer:
            headers["Referer"] = referer
        return headers


class CivitaiHashProvider(BaseProvider):
    """
    [v3.0.1] 通过 SHA256 哈希精确匹配 Civitai 模型
    
    Civitai 官方 API: /api/v1/model-versions/by-hash/{hash}
    参考: ComfyUI-Lora-Manager 实现
    
    准确率: 100% (对于从 Civitai 下载的模型)
    """
    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://civitai.com/api/v1/model-versions/by-hash"
        self._hash_cache = {}  # 缓存已计算的哈希
    
    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """计算文件 SHA256 哈希 (支持大文件)"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):  # 64KB chunks
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def search_by_hash(self, file_path: str, original_filename: str):
        """Search Civitai by SHA256"""
        if getattr(self, "circuit_open", False):
            print(f"[CivitaiProvider] Circuit Open (Blocking skipped)")
            await asyncio.sleep(0) # Yield
            return None

        # Calculate Hash (Async)
        # ...
        
        try:
            # ... request ...
            pass
        except Exception as e:
            if "403" in str(e):
                self.error_count = getattr(self, "error_count", 0) + 1
                if self.error_count >= 3:
                    self.circuit_open = True
                    print(f"[CivitaiProvider] 403 limit reached. Disabling Civitai for this session.")
            return None
        """
        通过文件哈希精确匹配 Civitai 模型
        
        Args:
            file_path: 本地文件完整路径
            original_filename: 原始文件名
            
        Returns:
            list: 匹配结果列表 (0或1个结果)
        """
        results = []
        
        if not os.path.exists(file_path):
            print(f"[CivitaiHash] File not found: {file_path}")
            return results
        
        try:
            # 检查缓存
            if file_path in self._hash_cache:
                file_hash = self._hash_cache[file_path]
            else:
                print(f"[CivitaiHash] Calculating SHA256 for: {original_filename}")
                # [Optimization] Run hashing in a separate thread to avoid blocking the Event Loop
                file_hash = await asyncio.to_thread(self.calculate_sha256, file_path)
                self._hash_cache[file_path] = file_hash
                print(f"[CivitaiHash] Hash: {file_hash[:16]}...")
            
            # [v3.0.3] 调用 Civitai API - 添加 Origin/Referer 绕过 Cloudflare
            headers = self._get_headers("https://civitai.com")
            headers["Origin"] = "https://civitai.com"
            headers["Referer"] = "https://civitai.com/"
            
            token = self.config.get("civitai_api_key")
            if token:
                headers["Authorization"] = f"Bearer {token}"
                print(f"[CivitaiHash] Using API Key: {token[:8]}...")
            else:
                print(f"[CivitaiHash] Warning: No API Key configured")

            
            url = f"{self.api_url}/{file_hash}"
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        model_id = data.get("modelId")
                        model_name = data.get("model", {}).get("name", "Unknown")
                        version_name = data.get("name", "")
                        
                        # 构建下载 URL
                        download_url = data.get("downloadUrl", "")
                        if not download_url:
                            # 回退到标准模型页面
                            download_url = f"https://civitai.com/models/{model_id}"
                        
                        results.append({
                            "source": "Civitai (Hash Match)",
                            "name": f"{model_name} - {version_name}",
                            "filename": original_filename,
                            "url": download_url,
                            "pageUrl": f"https://civitai.com/models/{model_id}",
                            "score": 1.0,  # 100% 确定匹配
                            "hash_match": True
                        })
                        
                        print(f"[CivitaiHash] ✓ Exact match found: {model_name}")
                        
                    except Exception as e:
                        print(f"[CivitaiHash] Parse error: {e}")
                        
                elif response.status_code == 404:
                    print(f"[CivitaiHash] No match for hash (model may not be from Civitai)")
                else:
                    print(f"[CivitaiHash] API returned {response.status_code}")
                    
        except Exception as e:
            print(f"[CivitaiHash] Error: {e}")
        
        return results


class CivitaiProvider(BaseProvider):

    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://civitai.com/api/v1/models"
    
    async def search(self, query, original_filename):
        results = []
        try:
            print(f"[CivitaiProvider] Searching API for: {query}")
            headers = self._get_headers("https://civitai.com")
            
            # [Fix] Add Origin/Referer to satisfy Cloudflare/Anti-bot checks
            headers["Origin"] = "https://civitai.com"
            headers["Referer"] = "https://civitai.com/"
            
            token = self.config.get("civitai_api_key")
            if token:
                headers["Authorization"] = f"Bearer {token}"
                # Log that key is being used (masked)
                print(f"[CivitaiProvider] Authenticated search (Key ends found)")

            encoded_query = urllib.parse.quote(query)
            # Fetch more results to increase hit rate
            url = f"{self.api_url}?query={encoded_query}&limit=20"
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                if response.status_code != 200: 
                    print(f"[CivitaiProvider] API Error {response.status_code} (Check API Key or Network)")
                    # Detailed debug for 403
                    if response.status_code == 403:
                        print(f"[CivitaiProvider] 403 Forbidden. Headers sent: {headers.keys()}")
                    return []
                
                try:
                    data = response.json()
                except: return []

                items = data.get("items", [])
                original_lower = original_filename.lower()
                
                for item in items:
                    model_name = item.get("name", "")
                    model_id = item.get("id")
                    
                    for version in item.get("modelVersions", []):
                        ver_name = version.get("name", "")
                        ver_id = version.get("id")
                        
                        for file_info in version.get("files", []):
                            fname = file_info.get("name", "")
                            if not fname: continue
                            
                            # Scoring
                            fname_base = os.path.splitext(fname)[0].lower()
                            file_score = AdvancedTokenizer.calculate_similarity(original_lower, fname_base)
                            
                            # Strict exclusion
                            if file_score <= 0.05: continue
                            
                            combined_name = f"{model_name} {ver_name}"
                            name_score = AdvancedTokenizer.calculate_similarity(original_lower, combined_name.lower())
                            
                            # Final weighted score
                            final_score = max(file_score, (file_score * 0.7 + name_score * 0.3))
                            
                            if final_score > 0.35:
                                results.append({
                                    "source": "Civitai (Native)",
                                    "name": f"{model_name} - {ver_name}",
                                    "filename": fname,
                                    "url": file_info.get("downloadUrl"),
                                    "pageUrl": f"https://civitai.com/models/{model_id}?modelVersionId={ver_id}",
                                    "score": final_score
                                })
        except Exception as e:
            print(f"[CivitaiProvider] Error: {e}")
        return results

class HuggingFaceProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://huggingface.co/api/models"

    async def search(self, query, original_filename):
        results = []
        try:
            print(f"[HFProvider] Searching API for: {query}")
            headers = self._get_headers("https://huggingface.co")
            encoded_query = urllib.parse.quote(query)
            url = f"{self.api_url}?search={encoded_query}&limit=20"
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                if response.status_code != 200: return []
                
                try:
                    data = response.json()
                except: return []
                
                original_lower = original_filename.lower()
                
                for repo in data:
                    model_id = repo.get("modelId", "")
                    if not model_id: continue
                    
                    repo_name_clean = model_id.split("/")[-1]
                    
                    score = AdvancedTokenizer.calculate_similarity(original_lower, repo_name_clean.lower())
                    full_score = AdvancedTokenizer.calculate_similarity(original_lower, model_id.lower().replace("/", " "))
                    final_score = max(score, full_score)
                    
                    if final_score > 0.35:
                        results.append({
                            "source": "HuggingFace",
                            "name": model_id,
                            "filename": f"{repo_name_clean}.safetensors", 
                            "url": f"https://huggingface.co/{model_id}/tree/main",
                            "pageUrl": f"https://huggingface.co/{model_id}",
                            "score": final_score
                        })
        except Exception as e:
            print(f"[HFProvider] Error: {e}")
        return results

class HuggingFaceFileSearchProvider(BaseProvider):
    """
    [v3.3.0] 高性能 HuggingFace 文件搜索
    
    优化策略：
    1. 并发目录遍历 (asyncio.gather)
    2. 智能剪枝 (仅扫描相关目录)
    3. 仓库结构缓存 (5分钟TTL)
    4. 早停机制 (找到匹配立即返回)
    """
    
    # 类级别缓存 (所有实例共享)
    _tree_cache = {}  # {model_id: {"tree": {...}, "ts": timestamp}}
    CACHE_TTL = 300   # 5 分钟
    
    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://huggingface.co/api/models"
        
    def _extract_keywords(self, filename):
        """从文件名提取搜索关键词"""
        base_name = os.path.splitext(filename)[0].lower()
        # 分词
        parts = re.split(r'[-_.\s]+', base_name)
        # 过滤噪声
        noise = {'average', 'rank', 'bf16', 'fp16', 'fp8', 'safetensors', 'ckpt', 
                 'q4', 'q5', 'q8', 'k', 'm', 's', 'single', 'merged'}
        keywords = [p for p in parts if len(p) >= 2 and p not in noise and not p.isdigit()]
        return set(keywords[:6])  # 最多 6 个关键词
        
    async def search(self, query, original_filename):
        """高性能搜索入口"""
        import time
        start_time = time.time()
        results = []
        
        try:
            keywords = self._extract_keywords(original_filename)
            if not keywords:
                return []
            
            # 智能仓库检测
            base_lower = original_filename.lower()
            priority_repos = []
            
            # WAN 视频模型 -> Kijai/WanVideo_comfy
            if 'wan' in base_lower:
                priority_repos.append("Kijai/WanVideo_comfy")
            # Hunyuan -> Kijai/HunyuanVideo_comfy  
            if 'hunyuan' in base_lower:
                priority_repos.append("Kijai/HunyuanVideo_comfy")
            # LTX -> Kijai
            if 'ltx' in base_lower:
                priority_repos.append("Kijai/LTXVideo_comfy")
                
            headers = self._get_headers("https://huggingface.co")
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                
                # Phase 1: 优先搜索已知仓库
                for repo_id in priority_repos:
                    print(f"[HFOptimized] Priority scan: {repo_id}")
                    result = await self._scan_repo_concurrent(session, repo_id, keywords, original_filename)
                    if result:
                        elapsed = time.time() - start_time
                        print(f"[HFOptimized] Found in {elapsed:.2f}s")
                        return [result]
                
                # Phase 2: API 搜索其他仓库
                search_queries = [" ".join(list(keywords)[:3])]
                if 'lora' in base_lower:
                    search_queries.append(f"{list(keywords)[0] if keywords else ''} Kijai")
                
                all_repos = []
                for sq in search_queries[:2]:
                    encoded = urllib.parse.quote(sq)
                    url = f"{self.api_url}?search={encoded}&limit=5"
                    resp = await session.get(url)
                    if resp.status_code == 200:
                        try:
                            repos = resp.json()
                            for r in repos:
                                mid = r.get("modelId", "")
                                if mid and mid not in [x.get("modelId") for x in all_repos]:
                                    if mid not in priority_repos:  # 避免重复扫描
                                        all_repos.append(r)
                        except:
                            pass
                
                # Phase 3: 并发扫描候选仓库
                tasks = []
                for repo in all_repos[:5]:  # 最多 5 个仓库
                    model_id = repo.get("modelId", "")
                    if model_id:
                        tasks.append(self._scan_repo_concurrent(session, model_id, keywords, original_filename))
                
                if tasks:
                    # 使用 as_completed 实现早停
                    for coro in asyncio.as_completed(tasks):
                        try:
                            result = await coro
                            if result and result.get("score", 0) >= 0.9:
                                elapsed = time.time() - start_time
                                print(f"[HFOptimized] Found in {elapsed:.2f}s")
                                return [result]
                            elif result:
                                results.append(result)
                        except Exception as e:
                            print(f"[HFOptimized] Task error: {e}")
                
                elapsed = time.time() - start_time
                print(f"[HFOptimized] Completed in {elapsed:.2f}s, found {len(results)} results")
                
        except Exception as e:
            print(f"[HFOptimized] Error: {e}")
        
        return sorted(results, key=lambda x: x.get("score", 0), reverse=True)[:3]
    
    async def _scan_repo_concurrent(self, session, model_id, keywords, original_filename):
        """并发扫描仓库目录"""
        import time
        
        try:
            # 检查缓存
            cache_key = model_id
            now = time.time()
            
            if cache_key in self._tree_cache:
                cached = self._tree_cache[cache_key]
                if now - cached["ts"] < self.CACHE_TTL:
                    tree = cached["tree"]
                    return self._search_in_tree(tree, model_id, keywords, original_filename)
            
            # 获取根目录
            tree_url = f"https://huggingface.co/api/models/{model_id}/tree/main"
            resp = await session.get(tree_url)
            if resp.status_code != 200:
                return None
            
            root_items = resp.json()
            
            # 构建树结构 (并发获取子目录)
            tree = {"files": [], "dirs": {}}
            dir_tasks = []
            
            for item in root_items:
                item_type = item.get("type", "")
                item_path = item.get("path", "")
                
                if item_type == "file":
                    tree["files"].append(item_path)
                elif item_type == "directory":
                    # 智能剪枝：只扫描与关键词相关的目录
                    dir_lower = item_path.lower()
                    should_scan = any(kw in dir_lower for kw in keywords)
                    # 也扫描常见目录名
                    common_dirs = {'lora', 'loras', 'models', 'checkpoints', 'weights'}
                    if any(cd in dir_lower for cd in common_dirs):
                        should_scan = True
                    
                    if should_scan:
                        dir_tasks.append(self._get_dir_files(session, model_id, item_path))
            
            # 并发获取所有相关子目录
            if dir_tasks:
                dir_results = await asyncio.gather(*dir_tasks, return_exceptions=True)
                for i, result in enumerate(dir_results):
                    if isinstance(result, dict):
                        dir_path = list(result.keys())[0] if result else None
                        if dir_path:
                            tree["dirs"][dir_path] = result[dir_path]
            
            # 缓存树结构
            self._tree_cache[cache_key] = {"tree": tree, "ts": now}
            
            # 在树中搜索
            return self._search_in_tree(tree, model_id, keywords, original_filename)
            
        except Exception as e:
            print(f"[HFOptimized] Repo scan error for {model_id}: {e}")
            return None
    
    async def _get_dir_files(self, session, model_id, dir_path, depth=0):
        """递归获取目录文件 (最多2层)"""
        result = {dir_path: {"files": [], "dirs": {}}}
        
        if depth >= 2:  # 限制深度
            return result
        
        try:
            url = f"https://huggingface.co/api/models/{model_id}/tree/main/{dir_path}"
            resp = await session.get(url)
            if resp.status_code != 200:
                return result
            
            items = resp.json()
            sub_dir_tasks = []
            
            for item in items:
                item_type = item.get("type", "")
                item_path = item.get("path", "")
                
                if item_type == "file":
                    result[dir_path]["files"].append(item_path)
                elif item_type == "directory" and depth < 1:  # 只递归1层
                    sub_dir_tasks.append(self._get_dir_files(session, model_id, item_path, depth + 1))
            
            if sub_dir_tasks:
                sub_results = await asyncio.gather(*sub_dir_tasks, return_exceptions=True)
                for sr in sub_results:
                    if isinstance(sr, dict):
                        result[dir_path]["dirs"].update(sr)
                        
        except Exception as e:
            print(f"[HFOptimized] Dir error {dir_path}: {e}")
        
        return result
    
    def _search_in_tree(self, tree, model_id, keywords, original_filename):
        """在缓存的树结构中搜索文件"""
        original_lower = original_filename.lower()
        original_base = os.path.splitext(original_filename)[0].lower()
        
        # 搜索根目录文件
        for file_path in tree.get("files", []):
            if self._is_match(file_path, original_lower, original_base):
                return self._build_result(model_id, file_path, 0.98)
        
        # 搜索子目录
        for dir_path, dir_content in tree.get("dirs", {}).items():
            for file_path in dir_content.get("files", []):
                if self._is_match(file_path, original_lower, original_base):
                    return self._build_result(model_id, file_path, 0.95)
            
            # 搜索嵌套子目录
            for sub_dir, sub_content in dir_content.get("dirs", {}).items():
                if isinstance(sub_content, dict):
                    for file_path in sub_content.get("files", []):
                        if self._is_match(file_path, original_lower, original_base):
                            return self._build_result(model_id, file_path, 0.92)
        
        return None
    
    def _is_match(self, file_path, original_lower, original_base):
        """检查文件是否匹配"""
        file_lower = file_path.lower()
        file_base = os.path.splitext(os.path.basename(file_path))[0].lower()
        
        # 精确匹配文件名
        if original_base in file_base or file_base in original_base:
            return True
        
        # 包含原始文件名
        if original_lower in file_lower:
            return True
        
        return False
    
    def _build_result(self, model_id, file_path, score):
        """构建结果对象"""
        return {
            "source": "HuggingFace (Exact File)",
            "name": model_id,
            "filename": file_path,
            "url": f"https://huggingface.co/{model_id}/resolve/main/{file_path}",
            "pageUrl": f"https://huggingface.co/{model_id}/tree/main",
            "score": score
        }




class ModelScopeProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://modelscope.cn/api/v1/dolphin/models"

    async def search(self, query, original_filename):
        results = []
        try:
            print(f"[ModelScopeProvider] Searching API for: {query}")
            headers = self._get_headers(referer="https://modelscope.cn/models")
            headers["Content-Type"] = "application/json"
            headers["Origin"] = "https://modelscope.cn"
            
            payload = {
                "PageSize": 20, 
                "PageNumber": 1, 
                "SearchText": query, 
                "Sort": {"SortBy": "Default"}
            }
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.put(self.api_url, json=payload)
                if response.status_code != 200: return []
                
                try:
                    data = response.json()
                except: return []
                
                if not data.get("Success", False): return []
                models = data.get("Data", {}).get("Model", {}).get("Models", [])
                
                original_lower = original_filename.lower()
                
                for model in models:
                    org_name = model.get("Path", "")
                    model_name = model.get("Name", "")
                    chinese_name = model.get("ChineseName", "")
                    
                    full_path_cleansed = org_name.split("/")[-1] if "/" in org_name else org_name
                    
                    scores = [
                        AdvancedTokenizer.calculate_similarity(original_lower, model_name.lower()),
                        AdvancedTokenizer.calculate_similarity(original_lower, full_path_cleansed.lower()),
                    ]
                    if chinese_name:
                        scores.append(AdvancedTokenizer.calculate_similarity(original_lower, chinese_name.lower()))
                        
                    score = max(scores)
                    
                    if score > 0.35:
                        results.append({
                            "source": "ModelScope",
                            "name": chinese_name if chinese_name else model_name,
                            "filename": "Unknown (Go to Files)",
                            "url": f"https://modelscope.cn/models/{org_name}/files",
                            "pageUrl": f"https://modelscope.cn/models/{org_name}",
                            "score": score
                        })
        except Exception as e:
            print(f"[ModelScopeProvider] Error: {e}")
        return results

class GoogleOmniProvider(BaseProvider):
    """
    Search multiple platforms via Google using Parsel for extraction.
    """
    def __init__(self, config):
        super().__init__(config)
        
    async def search(self, query, original_filename):
        results = []
        try:
            # 使用域名作为关键词，不使用 site: 语法 (容易触发率限制)
            sites_or_keywords = "liblib OR shakker OR civitai OR huggingface OR modelscope"
            full_query = f"{query} ({sites_or_keywords})"
            
            print(f"[GoogleOmni] Searching: {full_query}")
            
            encoded_query = urllib.parse.quote(full_query)
            url = f"https://www.google.com/search?q={encoded_query}&num=20&hl=en"
            
            headers = self._get_headers("https://www.google.com/")
            
            # 添加随机延迟避免触发率限制
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                if response.status_code != 200: return []
                
                html = response.text
                selector = Selector(text=html)
                
                # Robust extraction using CSS Selectors and Regex Fallback
                # 1. Standard Google Results: div.g a href
                # 2. Raw URL regex fallback
                
                found_urls = set()
                
                # CSS Approach: Select main Result links
                # Usually: div#search div.g a (but class names change)
                # Generic: a[href^="http"]:has(h3) -> more robust
                
                # Also try generic all links if specific selector fails
                # FIX: Use 'a::attr(href)' to get ALL links, including relative ones like /url?q=...
                # Previous 'a[href^="http"]' missed Google's redirect links
                css_links = selector.css('a::attr(href)').getall()
                for link in css_links:
                    # Case 1: Google Redirect Link (/url?q=https://...)
                    if link.startswith("/url?q="):
                         match = re.search(r'url\?q=([^"&]+)', link)
                         if match: 
                             found_urls.add(urllib.parse.unquote(match.group(1)))
                    
                    # Case 2: Direct HTTP Link (e.g. Knowledge Graph, some layouts)
                    elif link.startswith("http"):
                         if "google.com" not in link and "googleusercontent" not in link:
                              found_urls.add(link)
                
                original_lower = original_filename.lower()
                
                for u in found_urls:
                    try:
                        decoded_url = urllib.parse.unquote(u)
                        if not decoded_url.startswith("http"): continue
                        
                        meta = self._parse_link(decoded_url, original_lower)
                        if meta and meta["score"] > 0.35:
                            results.append(meta)
                    except: pass
                            
        except Exception as e:
            print(f"[GoogleOmni] Error: {e}")
        return results

    def _parse_link(self, url, original_lower):
        score = 0
        name = ""
        source = "Google"
        url = url.lower()
        
        # Domain parsing
        if "civitai.com/models/" in url:
            source = "Civitai (Google)"
            name = "Civitai Model"
        elif "huggingface.co" in url:
            # Allow blob if it is a model file
            if "blob" in url and not any(ext in url for ext in [".safetensors", ".gguf", ".pt", ".pth", ".bin", ".onnx"]):
                return None
            source = "HuggingFace (Google)"
            name = url.split("huggingface.co/")[-1].split("/")[0]
        elif "modelscope.cn/models" in url:
            source = "ModelScope (Google)"
            name = "ModelScope Model"
        elif "liblib.art" in url:
            source = "Liblib (Google)"
            name = "Liblib Model"
        elif "shakker.ai" in url:
            source = "Shakker (Google)"
            name = "Shakker Model"
        else:
            return None

        clean_url = urllib.parse.unquote(url)
        score = AdvancedTokenizer.calculate_similarity(original_lower, clean_url)
        
        return {
            "source": source,
            "name": name,
            "filename": "Direct Link (Click to Visit)",
            "url": clean_url, 
            "pageUrl": clean_url,
            "score": score
        }

class LiblibProvider(BaseProvider):
    """
    Search models on liblib.art (哩布哩布) via HTML scraping.
    Liblib 是国内最大的 AI 模型社区之一。
    """
    def __init__(self, config):
        super().__init__(config)
        self.search_url = "https://www.liblib.art/search"
        
    async def search(self, query, original_filename):
        results = []
        try:
            print(f"[LiblibProvider] Searching: {query}")
            
            encoded_query = urllib.parse.quote(query)
            url = f"{self.search_url}?keyword={encoded_query}"
            
            headers = self._get_headers("https://www.liblib.art/")
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                if response.status_code != 200:
                    print(f"[LiblibProvider] Status {response.status_code}")
                    return []
                
                html = response.text
                selector = Selector(text=html)
                
                # Liblib 搜索结果页面使用动态 JS 渲染
                # 尝试解析静态内容中的模型卡片链接
                links = selector.css('a[href*="/modelinfo/"]::attr(href)').getall()
                
                original_lower = original_filename.lower()
                seen_urls = set()
                
                for link in links[:10]:
                    if link in seen_urls:
                        continue
                    seen_urls.add(link)
                    
                    if link.startswith("/"):
                        full_url = f"https://www.liblib.art{link}"
                    elif link.startswith("http"):
                        full_url = link
                    else:
                        continue
                    
                    model_id = link.split("/modelinfo/")[-1].split("/")[0] if "/modelinfo/" in link else "Liblib Model"
                    
                    score = AdvancedTokenizer.calculate_similarity(original_lower, model_id.lower())
                    
                    if score > 0.3:
                        results.append({
                            "source": "Liblib",
                            "name": model_id,
                            "filename": "Direct Link (Click to Visit)",
                            "url": full_url,
                            "pageUrl": full_url,
                            "score": score
                        })
                        
        except Exception as e:
            print(f"[LiblibProvider] Error: {e}")
        return results

class DuckDuckGoProvider(BaseProvider):
    """
    Search multiple platforms via DuckDuckGo HTML version.
    This is much more robust against blocking than Google scraping.
    """
    def __init__(self, config):
        super().__init__(config)
        self.impersonate = None # DDG HTML doesn't need chrome impersonation, just standard headers
        
    async def search(self, query, original_filename):
        results = []
        try:
            # 使用域名作为关键词，不使用 site: 语法 (DDG 对 site: 支持不稳定)
            sites = "liblib OR shakker OR civitai OR huggingface OR modelscope"
            full_query = f"{query} ({sites})"
            
            print(f"[DuckDuckGo] Searching: {full_query}")
            
            url = "https://html.duckduckgo.com/html/"
            data = {"q": full_query}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://html.duckduckgo.com/"
            }
            
            # [v3.3.1] 删除延迟，依赖连接复用
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.post(url, data=data)
                if response.status_code != 200: 
                    print(f"[DuckDuckGo] Status {response.status_code}")
                    return []
                
                html = response.text
                selector = Selector(text=html)
                
                # DDG HTML results
                # div.result -> a.result__a (title), a.result__url (url)
                result_divs = selector.css('div.result')
                
                original_lower = original_filename.lower()
                
                for div in result_divs:
                    raw_url = div.css('a.result__a::attr(href)').get()
                    if not raw_url: continue
                    
                    decoded_url = urllib.parse.unquote(raw_url)
                    if not decoded_url.startswith("http"): continue
                    
                    meta = self._parse_link(decoded_url, original_lower)
                    if meta and meta["score"] > 0.35:
                        results.append(meta)
                            
        except Exception as e:
            print(f"[DuckDuckGo] Error: {e}")
        return results

    def _parse_link(self, url, original_lower):
        # Reuse logic from GoogleOmniProvider via helper or copy
        # For now, duplicate standard parsing logic for self-containment
        name = "Online Model"
        source = "DuckDuckGo"
        url_lower = url.lower()
        
        if "civitai.com/models/" in url_lower:
            source = "Civitai (DDG)"; name = "Civitai Model"
        elif "huggingface.co" in url_lower:
            if "blob" in url_lower and not any(ext in url_lower for ext in [".safetensors", ".gguf", ".pt", ".pth", ".bin", ".onnx"]): return None
            source = "HuggingFace (DDG)"
            # Fix: Extract full repo "user/repo" not just "user"
            # url_lower: https://huggingface.co/FX-FeiHou/wan2.2-Remix/...
            parts = url_lower.split("huggingface.co/")[-1].split("/")
            if len(parts) >= 2:
                name = f"{parts[0]}/{parts[1]}"
            else:
                name = parts[0]
        elif "modelscope.cn/models" in url_lower:
            source = "ModelScope (DDG)"; name = "ModelScope Model"
        elif "liblib.art" in url_lower:
            source = "Liblib (DDG)"; name = "Liblib Model"
        elif "shakker.ai" in url_lower:
            source = "Shakker (DDG)"; name = "Shakker Model"
        else: return None

        score = AdvancedTokenizer.calculate_similarity(original_lower, urllib.parse.unquote(url_lower))
        
        return {
            "source": source,
            "name": name,
            "filename": "Direct Link (Click to Visit)",
            "url": urllib.parse.unquote(url),
            "pageUrl": urllib.parse.unquote(url),
            "score": score
        }

class ModelSearcher:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        self.config = self.load_config()
        self.search_cache = {}
        
        # Provider 优先级 [v3.0.1]:
        # 1. CivitaiHashProvider (100% 精确匹配，需要本地文件路径)
        # 2. HuggingFace File Search (精确文件名匹配)
        # 3. Civitai (文本搜索) > HuggingFace API > Liblib > ModelScope > Google (兜底)
        
        self.hash_provider = CivitaiHashProvider(self.config)  # [v3.0.1] SHA256 精确匹配
        
        self.providers = [
            HuggingFaceFileSearchProvider(self.config),  # [v3.0] 精确文件名搜索
            CivitaiProvider(self.config),
            HuggingFaceProvider(self.config),
            LiblibProvider(self.config),
            ModelScopeProvider(self.config),
            GoogleOmniProvider(self.config),
            DuckDuckGoProvider(self.config)
        ]



    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {"civitai_api_key": ""}

    def get_config(self):
        return self.config

    def save_config(self, new_config):
        self.config.update(new_config)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except: pass
        
    async def validate_api_key(self, api_key):
        if not api_key: return False, "Empty API Key"
        # Validate using curl_cffi
        try:
            async with AsyncSession(impersonate="chrome120", timeout=10) as session:
                resp = await session.get("https://civitai.com/api/v1/models?limit=1", 
                                       headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200: return True, "Valid API Key"
                if resp.status_code == 401: return False, "Invalid API Key"
                return False, f"Status: {resp.status_code}"
        except Exception as e:
            return False, str(e)

    async def search(self, filename, ignore_cache=False, file_path=None):
        """
        在线搜索模型匹配
        
        Args:
            filename: 原始文件名
            ignore_cache: 是否忽略缓存
            file_path: [v3.0.1] 可选，本地文件完整路径 (用于 SHA256 哈希匹配)
        """
        if not filename: return None

        # [Strict Filter] Verify extension
        from .scanner import is_valid_model_file
        if not is_valid_model_file(filename):
            print(f"[AutoMatch] Skipped non-model file: {filename}")
            return None
        
        if not ignore_cache and filename in self.search_cache:
            print(f"[AutoMatch] Cache Hit: {filename}")
            return self.search_cache[filename]
        
        # [v3.0.1] 优先尝试 SHA256 哈希匹配 (100% 精确)
        if file_path and os.path.exists(file_path):
            try:
                hash_results = await self.hash_provider.search_by_hash(file_path, filename)
                if hash_results:
                    best = hash_results[0]
                    print(f"[AutoMatch] ✓ Hash Match: {best['name']} (100% accurate)")
                    self.search_cache[filename] = best
                    return best
            except Exception as e:
                print(f"[AutoMatch] Hash search failed: {e}")

        repo_id, matched_key = AdvancedTokenizer.lookup_popular_model(filename)
        if repo_id:
            res = {
                "url": f"https://huggingface.co/{repo_id}/tree/main",
                "source": "HuggingFace (Official)",
                "name": repo_id,
                "pageUrl": f"https://huggingface.co/{repo_id}",
                "score": 1.0
            }
            self.search_cache[filename] = res
            return res

        search_terms = AdvancedTokenizer.extract_search_terms(filename)
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        # [v3.3.1] 极限优化: 单轮全量并发
        # 只使用最优搜索词，所有 Provider 同时启动
        best_term = search_terms[0] if search_terms else base_name
        print(f"[AutoMatch] Searching: {filename} | Term: {best_term}")
        
        import time
        start_time = time.time()
        
        all_candidates = []
        
        # 启动所有 Provider 任务
        tasks = [provider.search(best_term, base_name) for provider in self.providers]
        
        # 使用 as_completed 实现早停
        for future in asyncio.as_completed(tasks):
            try:
                res = await future
                if res and isinstance(res, list):
                    all_candidates.extend(res)
                    
                    # 早停检查: 任何 Provider 返回高分匹配立即停止
                    all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
                    if all_candidates and all_candidates[0].get("score", 0) >= 0.7:
                        elapsed = time.time() - start_time
                        print(f"[AutoMatch] Fast match in {elapsed:.2f}s: {all_candidates[0]['name']}")
                        break
                        
            except Exception as e:
                print(f"[AutoMatch] Provider task failed: {e}")
        
        elapsed = time.time() - start_time
        print(f"[AutoMatch] Completed in {elapsed:.2f}s")
        
        # Final Sort and Deduplication
        all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        unique_candidates = []
        seen_urls = set()
        for cand in all_candidates:
            url = cand.get("pageUrl", "")
            if url not in seen_urls:
                unique_candidates.append(cand)
                seen_urls.add(url)
                
        best_match = unique_candidates[0] if unique_candidates else None
        
        if best_match:
            print(f"[AutoMatch] Match Found: {best_match['name']} ({best_match['source']}) Score: {best_match['score']:.2f}")
        else:
            print(f"[AutoMatch] No match for: {filename}")
            
        self.search_cache[filename] = best_match
        return best_match
