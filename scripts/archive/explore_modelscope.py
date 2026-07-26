import asyncio
import aiohttp
import json

async def verified_api_test(model_id):
    """
    Test the API endpoint discovered from SDK reverse engineering:
    GET /api/v1/models/{model_id}/repo/files?Revision={revision}&Recursive={recursive}&Root={root}
    """
    print(f"Testing Verified API for: {model_id}")
    
    # Endpoint from SDK: get_model_files
    url = f"https://modelscope.cn/api/v1/models/{model_id}/repo/files"
    params = {
        "Revision": "master",
        "Recursive": "True",
        "Root": ""
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": f"https://modelscope.cn/models/{model_id}/files",
        # "X-Request-ID": "..." # SDK uses this, maybe optional?
    }
    
    print(f"Requesting: {url} with {params}")
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as resp:
            print(f"API Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
            else:
                print(await resp.text())

async def main():
    await verified_api_test("Qwen/Qwen2.5-7B-Instruct")

if __name__ == "__main__":
    asyncio.run(main())
