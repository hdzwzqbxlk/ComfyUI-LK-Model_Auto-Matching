import asyncio
import urllib.parse
import os
import json
import re
import random
from curl_cffi.requests import AsyncSession
from parsel import Selector

try:
    from .utils import AdvancedTokenizer
except ImportError:
    from utils import AdvancedTokenizer

class BaseProvider:
    def __init__(self, config=None):
        self.config = config or {}
        # Chrome 120 impersonation for Anti-Detect
        # curl_cffi supports this natively, works on Py3.8+ Windows/Linux/Mac
        self.impersonate = "chrome120"
        self.timeout = 15

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

class CivitaiProvider(BaseProvider):
    def __init__(self, config):
        super().__init__(config)
        self.api_url = "https://civitai.com/api/v1/models"
    
    async def search(self, query, original_filename):
        results = []
        try:
            print(f"[CivitaiProvider] Searching API for: {query}")
            headers = self._get_headers("https://civitai.com")
            token = self.config.get("civitai_api_key")
            if token:
                headers["Authorization"] = f"Bearer {token}"

            encoded_query = urllib.parse.quote(query)
            # Fetch more results to increase hit rate
            url = f"{self.api_url}?query={encoded_query}&limit=20"
            
            async with AsyncSession(impersonate=self.impersonate, headers=headers, timeout=self.timeout) as session:
                response = await session.get(url)
                if response.status_code != 200: 
                    print(f"[CivitaiProvider] API Error {response.status_code}")
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
            # Combined query
            sites_or_keywords = "liblib.art OR shakker.ai OR civitai.com OR huggingface.co OR modelscope.cn"
            full_query = f"{query} ({sites_or_keywords})"
            
            print(f"[GoogleOmni] Searching: {full_query}")
            
            encoded_query = urllib.parse.quote(full_query)
            url = f"https://www.google.com/search?q={encoded_query}&num=20&hl=en"
            
            headers = self._get_headers("https://www.google.com/")
            
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
                css_links = selector.css('a[href^="http"]::attr(href)').getall()
                for link in css_links:
                    if "google.com" not in link:
                         found_urls.add(link)
                    elif "/url?q=" in link:
                         match = re.search(r'url\?q=([^"&]+)', link)
                         if match: found_urls.add(urllib.parse.unquote(match.group(1)))
                
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

class ModelSearcher:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        self.config = self.load_config()
        self.search_cache = {}
        
        self.providers = [
            CivitaiProvider(self.config),
            HuggingFaceProvider(self.config),
            ModelScopeProvider(self.config),
            GoogleOmniProvider(self.config)
        ]

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {"civitai_api_key": ""}

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

    async def search(self, filename, ignore_cache=False):
        if not filename: return None
        
        if not ignore_cache and filename in self.search_cache:
            print(f"[AutoMatch] Cache Hit: {filename}")
            return self.search_cache[filename]

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
        
        print(f"[AutoMatch] Searching: {filename} | Terms: {search_terms}")
        
        all_candidates = []
        primary_term = search_terms[0] if search_terms else base_name
        
        # Concurrent Search
        tasks = []
        for provider in self.providers:
            tasks.append(provider.search(primary_term, base_name))
            
        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results_list:
            if isinstance(res, list):
                all_candidates.extend(res)
        
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
