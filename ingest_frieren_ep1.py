import asyncio
import os
import sys
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)

from db.connection import database as db
from services.ingestion.main import IngestionEngine

async def ingest_frieren():
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

    print(f"Mulai proses ingestion untuk Episode ID: {row['id']}...")
    engine = IngestionEngine()
    
    # We need to get the direct URL first to bypass cache if needed, but process_episode 
    # can also take direct_video_url. The ingest_pending.py does this:
    from services.stream_cache import get_cached_stream
    sources_response = await get_cached_stream(154587, 1.0)
    direct_url = ""
    if sources_response and "sources" in sources_response and len(sources_response["sources"]) > 0:
        direct_url = sources_response["sources"][0].get("url", "")
        
    print(f"Direct URL yang didapat: {direct_url}")
    
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
    print(f"URL Baru di DB: {updated['episodeUrl']}")
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(ingest_frieren())
