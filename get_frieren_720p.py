import asyncio
import os
import sys
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from db.connection import database as db
from services.stream_cache import get_cached_stream

async def fetch_ep(ep_num):
    try:
        res = await get_cached_stream(154587, ep_num)
        if res and "sources" in res:
            for s in res["sources"]:
                if s.get("quality") == "720p" and s.get("type") in ["mp4", "direct", "hls"]:
                    return ep_num, s.get("url")
            # Fallback to any 720p
            for s in res["sources"]:
                if s.get("quality") == "720p":
                    return ep_num, s.get("url")
    except Exception as e:
        return ep_num, f"Error: {e}"
    return ep_num, "Not found"

async def main():
    if not db.is_connected:
        await db.connect()
        
    print("Mengumpulkan link 720p untuk Frieren S1 (28 Episode)... (Proses ini memakan waktu beberapa detik karena scraping paralel)")
    
    # Frieren has 28 episodes. We'll scrape them concurrently with a limit.
    tasks = []
    sem = asyncio.Semaphore(5) # limit concurrency
    
    async def bounded_fetch(ep_num):
        async with sem:
            return await fetch_ep(ep_num)
            
    for i in range(1, 29):
        tasks.append(asyncio.create_task(bounded_fetch(float(i))))
        
    results = await asyncio.gather(*tasks)
    
    print("\n=== Kumpulan Tautan Resolusi 720p (Frieren) ===")
    for ep, link in sorted(results, key=lambda x: x[0]):
        print(f"Episode {int(ep)}: {link}")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())