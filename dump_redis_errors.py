import asyncio
import os
import sys
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)

from services.cache import upstash_keys, upstash_get

async def dump_errors():
    keys = await upstash_keys("ingest_error:*")
    if not keys:
        print("✅ Tidak ada pesan error ingestion di Redis.")
        return
    
    print(f"Ditemukan {len(keys)} pesan error:")
    for key in keys:
        val = await upstash_get(key)
        print(f"\n--- {key} ---")
        print(val)

if __name__ == "__main__":
    asyncio.run(dump_errors())