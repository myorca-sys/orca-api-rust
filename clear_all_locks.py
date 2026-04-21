import asyncio
import os
import sys
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)

from services.cache import upstash_keys, upstash_del

async def clear_all():
    print("Mencari semua lock dan ingest keys...")
    keys1 = await upstash_keys("ingest:*")
    keys2 = await upstash_keys("lock:ingest*")
    keys3 = await upstash_keys("lock:scrape*")
    
    all_keys = keys1 + keys2 + keys3
    if not all_keys:
        print("Tidak ada key yang perlu dihapus.")
        return
        
    print(f"Menghapus {len(all_keys)} keys...")
    for k in all_keys:
        await upstash_del(k)
        print(f"- Terhapus: {k}")

if __name__ == "__main__":
    asyncio.run(clear_all())