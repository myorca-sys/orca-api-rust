import asyncio
import os
import sys
import time
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from db.connection import database as db
from services.cache import upstash_keys, upstash_get

async def monitor():
    await db.connect()
    
    print("📡 Mulai memantau proses ingestion di Hugging Face Space...\n")
    for i in range(15):  # Monitor selama sekitar 1.5 menit (15 * 6s)
        # 1. Check Redis Locks
        keys_episode = await upstash_keys("ingest:*")
        
        # 2. Check DB status for Frieren (ID 154587) Ep 1
        row = await db.fetch_one(
            """
            SELECT "episodeUrl" 
            FROM episodes 
            WHERE "anilistId" = 154587 AND "episodeNumber" = 1 
            AND "providerId" = 'kuronime'
            """
        )
        
        status_msg = ""
        if row:
            url = row['episodeUrl']
            if 'tg-proxy' in url:
                status_msg = f"✅ SELESAI! Video siap ditonton.\n🔗 URL Proxy: {url[:60]}..."
            else:
                status_msg = f"⏳ Masih diproses (Belum masuk ke Telegram). URL Saat Ini: {url[:60]}..."
        else:
            status_msg = "❌ Episode Frieren (Kuronime) belum ada di DB."
            
        active_workers = ""
        if keys_episode:
            active_workers = f"🔥 FFmpeg sedang aktif memotong: {', '.join(keys_episode)}"
        else:
            active_workers = "💤 Tidak ada FFmpeg yang sedang berjalan di Redis Lock."
            
        print(f"[{time.strftime('%H:%M:%S')}] {active_workers}")
        print(f"[{time.strftime('%H:%M:%S')}] {status_msg}")
        print("-" * 50)
        
        if 'tg-proxy' in (row['episodeUrl'] if row else ""):
            break
            
        await asyncio.sleep(6)
        
    await db.disconnect()
    print("Pemantauan selesai.")

if __name__ == "__main__":
    asyncio.run(monitor())