import asyncio
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(".env")

from db.connection import database
from services.pipeline import resolve_episode_sources
from services.ingestion.main import IngestionEngine

async def reingest():
    await database.connect()
    engine = IngestionEngine()
    
    anilist_id = 206914
    ep_num = 2.0
    original_url = "https://v2.samehadaku.how/nippon-sangoku-episode-2/"
    provider_id = "samehadaku"
    
    query = """
        SELECT "id"
        FROM episodes
        WHERE "anilistId" = :aid AND "episodeNumber" = :ep AND "providerId" = :pid
    """
    row = await database.fetch_one(query, values={"aid": anilist_id, "ep": ep_num, "pid": provider_id})
    if not row:
        print("Episode tidak ditemukan di DB.")
        await database.disconnect()
        return
    
    ep_id = row["id"]
    print(f"Re-ingesting {original_url}...")
    try:
        from services.cache import upstash_del
        await upstash_del(f"video_cache:{original_url}")
    except:
        pass
        
    sources_payload = await resolve_episode_sources(original_url, provider_id)
    sources = [s for s in sources_payload.get("sources", []) if s.get("raw_url") is not None]
    
    if sources:
        best_source = None
        for s in sources:
            if "720p" in s.get("quality", "").lower():
                best_source = s
                break
        if not best_source: 
            best_source = sources[0]
            
        direct_url = best_source.get("raw_url")
        print(f"Direct URL: {direct_url}")
        
        # update DB with original url back just in case
        await database.execute('UPDATE episodes SET "episodeUrl" = :url WHERE id = :id', values={"url": original_url, "id": ep_id})

        await engine.process_episode(ep_id, anilist_id, provider_id, ep_num, direct_url)
        print("Selesai reingest!")
    else:
        print("Gagal dapat raw url.")
        
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(reingest())
