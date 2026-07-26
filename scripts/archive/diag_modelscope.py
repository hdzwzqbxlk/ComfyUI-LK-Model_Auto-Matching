
import asyncio
import aiohttp
import json

async def list_files(session, repo_id):
    print(f"\n--- Listing {repo_id} ---")
    url = f"https://modelscope.cn/api/v1/models/{repo_id}/repo/files"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    for revision in ["master", "main"]:
        params = {"Revision": revision, "Recursive": "True", "Root": ""}
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    raw_data = data.get("Data", {})
                    files = raw_data.get("Files", []) if isinstance(raw_data, dict) else []
                    print(f"Revision: {revision} | Found {len(files)} files.")
                    for f in files:
                        print(f" - {f.get('Name')}")
                    return
        except Exception as e:
            print(f"Error ({revision}): {e}")

async def main():
    async with aiohttp.ClientSession() as session:
        await list_files(session, "Wan-AI/Wan2.1-T2V-14B")

if __name__ == "__main__":
    asyncio.run(main())
