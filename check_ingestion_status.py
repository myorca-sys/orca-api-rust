import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

async def check_ingest_locks():
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        print("Missing Upstash credentials.")
        return
        
    from apps.api.services.cache import upstash_keys, upstash_get
    
    # Prefix untuk lock dari queue.py dan main.py
    keys_batch = await upstash_keys("lock:ingest_batch_trigger*")
    keys_episode = await upstash_keys("ingest:*")
    
    print("=== STATUS INGESTION LOKAL & CLOUD ===")
    
    if not keys_batch and not keys_episode:
        print("✅ Tidak ada proses ingestion yang sedang berjalan (Idle/Selesai).")
        return
        
    if keys_batch:
        print(f"\n⏳ Batch Ingestion Queue Aktif:")
        for key in keys_batch:
            data = await upstash_get(key)
            print(f"  - {key}: {data}")
            
    if keys_episode:
        print(f"\n⚙️ Pemotongan/Slicing Sedang Berjalan (Active Workers):")
        for key in keys_episode:
            # Lewati error log jika ada
            if "error" in key:
                continue
            data = await upstash_get(key)
            print(f"  - {key}: {data}")

if __name__ == "__main__":
    asyncio.run(check_ingest_locks())