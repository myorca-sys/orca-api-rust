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

async def ingest_frieren_720p():
    if not db.is_connected:
        await db.connect()
        
    print("Mencari Frieren Ep 1 di database...")
    row = await db.fetch_one(
        """
        SELECT id, "providerId", "episodeUrl" 
        FROM episodes 
        WHERE "anilistId" = 154587 AND "episodeNumber" = 1 
        AND "providerId" = 'kuronime'
        """
    )
    
    if not row:
        print("Episode 1 tidak ditemukan!")
        return

    print(f"Mulai proses ingestion 720p untuk Episode ID: {row['id']}...")
    engine = IngestionEngine()
    
    from services.stream_cache import get_cached_stream
    sources_response = await get_cached_stream(154587, 1.0)
    direct_url = ""
    
    if sources_response and "sources" in sources_response:
        # Prioritize 720p
        for s in sources_response["sources"]:
            if s.get("quality") == "720p" and s.get("type") in ["mp4", "direct", "hls"]:
                direct_url = s.get("url", "")
                break
        
        # Fallback if 720p not found
        if not direct_url:
            for s in sources_response["sources"]:
                if s.get("type") in ["mp4", "direct", "hls"]:
                    direct_url = s.get("url", "")
                    break
        
    print(f"Direct URL (720p) yang didapat: {direct_url}")
    if not direct_url:
        print("Gagal mendapatkan direct URL.")
        return
    
    print("Sedang men-slice dan meng-upload ke Telegram (Ini akan memakan waktu beberapa menit)...")
    success = await engine.process_episode(
        episode_id=row['id'],
        anilist_id=154587,
        provider_id=row['providerId'],
        episode_number=1.0,
        direct_video_url=direct_url
    )
    
    print(f"Hasil Ingestion: {success}")
    
    # Cek URL baru di DB
    updated = await db.fetch_one('SELECT "episodeUrl" FROM episodes WHERE id = :id', {"id": row['id']})
    if updated:
        print(f"URL Baru di DB: {updated['episodeUrl']}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(ingest_frieren_720p())