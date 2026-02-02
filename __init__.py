import server
from aiohttp import web
from .core.scanner import ModelScanner
from .core.matcher import ModelMatcher
from .core.searcher import ModelSearcher

__version__ = "3.5.1" # ModelScope深度集成 + 智能Provider路由 + BestMatch修复
__author__ = "LK"

# 初始化核心组件
scanner = ModelScanner()
matcher = ModelMatcher(scanner)
searcher = ModelSearcher()

# 注册 API 路由
@server.PromptServer.instance.routes.post("/auto-matcher/match")
async def match_models(request):
    try:
        data = await request.json()
        items = data.get("items", [])
        
        # 调用新版 matcher，传入列表
        matches = matcher.match(items)
        
        # 格式化返回结果
        results = []
        for m in matches:
            results.append({
                "id": m["id"],
                "node_type": m["node_type"],
                "widget_name": m["widget_name"], 
                "original": m["original_value"], 
                "new_value": m["matched_value"],
                "match_type": m.get("match_type", "Fuzzy")
            })
        
        return web.json_response({"matches": results})
    except Exception as e:
        print(f"[AutoModelMatcher] API Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/auto-matcher/search")
async def search_models(request):
    try:
        data = await request.json()
        # 预期输入: {"items": [{"current": "v1.5.ckpt"}, ...], "ignore_cache": boolean} 
        items = data.get("items", [])
        ignore_cache = data.get("ignore_cache", False)
        
        # 准备并发任务
        tasks = []
        original_filenames = []
        
        from .core.scanner import is_valid_model_file
        import asyncio
        
        # [v3.0.3] 并发搜索前，先进行本地扫描
        for item in items:
            filename = item.get("current")
            if not filename: continue
            
            # 1. 检查本地是否存在 (暴力搜索所有模型目录)
            local_path = scanner.find_local_file(filename)
            if local_path:
                # 如果本地找到了，直接返回特殊结果
                results.append({
                    "original": filename,
                    "result": {
                        "source": "Local Disk (Unindexed)",
                        "name": "Found Locally",
                        "filename": filename,
                        "url": "",  # 不需要下载
                        "pageUrl": "",
                        "score": 1.0,
                        "local_path": local_path,
                        "description": "File exists on disk but not in ComfyUI index. Please Refresh."
                    }
                })
                continue

            # 2. 本地没找到，加入网络搜索队列
            # Strict Filter at API level
            if is_valid_model_file(filename):
                tasks.append(searcher.search(filename, ignore_cache=ignore_cache))
                original_filenames.append(filename)

        
        if not tasks:
            return web.json_response({"downloads": []})
            
        # 并发执行所有搜索
        search_results = await asyncio.gather(*tasks)
        
        results = []
        for filename, result in zip(original_filenames, search_results):
            if result:
                results.append({
                    "original": filename,
                    "result": result
                })
        
        return web.json_response({"downloads": results})
    except Exception as e:
        print(f"[AutoModelMatcher] Search API Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/auto-matcher/refresh-index")
async def refresh_index(request):
    try:
        count = scanner.scan_incremental()
        return web.json_response({"status": "ok", "count": count})
    except Exception as e:
        print(f"[AutoModelMatcher] Index Refresh Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/auto-matcher/save-config")
async def save_config(request):
    try:
        data = await request.json()
        searcher.save_config(data)
        return web.json_response({"status": "ok"})
    except Exception as e:
        print(f"[AutoModelMatcher] Save Config Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/auto-matcher/validate-config")
async def validate_config(request):
    try:
        data = await request.json()
        api_key = data.get("civitai_api_key", "")
        is_valid, msg = await searcher.validate_api_key(api_key)
        return web.json_response({"valid": is_valid, "message": msg})
    except Exception as e:
        print(f"[AutoModelMatcher] Validate Config Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.get("/auto-matcher/get-config")
async def get_config(request):
    try:
        config = searcher.get_config()
        # Only return safe fields to frontend if needed, but for local tool it's fine
        return web.json_response(config)
    except Exception as e:
        print(f"[AutoModelMatcher] Get Config Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

# 插件目录配置
WEB_DIRECTORY = "./js"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("\033[34m[AutoModelMatcher] \033[0mLoaded successfully with API support.")
