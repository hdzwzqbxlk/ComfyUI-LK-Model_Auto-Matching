import server
from aiohttp import web
from .scanner import ModelScanner
from .matcher import ModelMatcher

# 初始化核心组件
scanner = ModelScanner()
matcher = ModelMatcher(scanner)

# 注册 API 路由
@server.PromptServer.instance.routes.post("/auto-matcher/match")
async def match_models(request):
    try:
        data = await request.json()
        # 预期输入: {"items": [{"id": 1, "type": "checkpoints", "current": "foo.ckpt"}, ...]}
        items = data.get("items", [])
        results = []
        
        # 刷新缓存 (优化点：可以加个时间限制，别每次都刷)
        matcher.refresh_models()

        for item in items:
            target_name = item.get("current")
            model_type = item.get("type") # e.g., "checkpoints"
            
            # ComfyUI 的 type 经常有点乱，这里做一个映射
            # 例如 CheckpointLoaderSimple 的 widget 名字通常叫 ckpt_name，但对应的 folder path key 是 checkpoints
            # 前端负责传正确的 folder type
            
            match_result = matcher.match(target_name, model_type)
            if match_result:
                results.append({
                    "id": item.get("id"),
                    "new_value": match_result,
                    "original": target_name
                })
        
        return web.json_response({"matches": results})
    except Exception as e:
        print(f"[AutoModelMatcher] API Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@server.PromptServer.instance.routes.post("/auto-matcher/trigger-scan")
async def trigger_scan(request):
    scanner.scan_all_models()
    return web.json_response({"status": "scanned"})

# 插件目录配置
WEB_DIRECTORY = "./js"
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("\033[34m[AutoModelMatcher] \033[0mLoaded successfully with API support.")
