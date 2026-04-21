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
from services.ingestion.main import IngestionEngine

async def ingest_manual():
    if not db.is_connected:
        await db.connect()
        
    print("Mencari Tensura S1 (101280) Ep 23 di database...")
    row = await db.fetch_one(
        """
        SELECT id, "providerId", "episodeUrl" 
        FROM episodes 
        WHERE "anilistId" = 101280 AND "episodeNumber" = 23
        AND "providerId" = 'samehadaku'
        LIMIT 1
        """
    )
    
    if not row:
        print("Episode 23 tidak ditemukan di provider samehadaku, mencoba provider lain...")
        row = await db.fetch_one(
            """
            SELECT id, "providerId", "episodeUrl" 
            FROM episodes 
            WHERE "anilistId" = 101280 AND "episodeNumber" = 23
            LIMIT 1
            """
        )
        if not row:
             print("Episode 23 sama sekali tidak ditemukan!")
             await db.disconnect()
             return

    print(f"Mulai proses ingestion MANUAL untuk Episode ID: {row['id']}...")
    engine = IngestionEngine()
    
    direct_url = "https://pixeldrain.com/api/file/rYUUkSdm"
    
    print(f"Menggunakan URL direct paksaan: {direct_url}")
    print("Sedang men-download, men-slice, dan meng-upload ke Telegram...")
    print("MOHON TUNGGU (Kira-kira 10 Menit karena kecepatan Pixeldrain 0.19 MB/s)...")
    
    success = await engine.process_episode(
        episode_id=row['id'],
        anilist_id=101280,
        provider_id=row['providerId'],
        episode_number=23.0,
        direct_video_url=direct_url
    )
    
    print(f"Hasil Ingestion: {success}")
    
    # Cek URL baru di DB
    updated = await db.fetch_one('SELECT "episodeUrl" FROM episodes WHERE id = :id', {"id": row['id']})
    if updated:
        print(f"URL Baru di DB: {updated['episodeUrl']}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(ingest_manual())