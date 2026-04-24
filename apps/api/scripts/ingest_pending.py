import asyncio
import os
import sys
import argparse
from dotenv import load_dotenv

API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, API_DIR)

load_dotenv(os.path.join(API_DIR, ".env"))

from db.connection import database as db
from services.ingestion.main import IngestionEngine
from services.stream_cache import get_cached_stream

async def ingest_pending(limit: int):
    print(f"🚀 Memulai GitHub Actions Worker: Mencari maksimal {limit} episode tertunda...")
    
    # Pastikan database terkoneksi sebelum dipakai di query dan get_cached_stream
    should_disconnect = False
    if not db.is_connected:
        await db.connect()
        should_disconnect = True
        
    # Cari episode yang URL-nya belum tg-proxy
    query = """
        SELECT id, "anilistId", "episodeNumber", "episodeUrl" 
        FROM episodes 
        WHERE "episodeUrl" NOT LIKE '%tg-proxy%' 
        AND "episodeUrl" NOT LIKE '%workers.dev%'
        AND "episodeUrl" LIKE 'http%'
        ORDER BY "updatedAt" DESC 
        LIMIT :limit
    """
    rows = await db.fetch_all(query, values={"limit": limit})
    
    if not rows:
        print("✅ Tidak ada episode yang perlu di-ingest. Semua up-to-date!")
        if should_disconnect:
            await db.disconnect()
        return

    engine = IngestionEngine()
    
    for row in rows:
        ep_id = row['id']
        aid = row['anilistId']
        ep_num = float(row['episodeNumber'])
        
        print(f"\n--- Memproses {aid} Ep {ep_num} ---")
        
        sources_response = await get_cached_stream(aid, ep_num)
        if sources_response and "sources" in sources_response and len(sources_response["sources"]) > 0:
            direct_url = ""
            provider_id = "unknown"
            
            # Prioritize 720p
            for s in sources_response["sources"]:
                if s.get("quality") == "720p" and s.get("type") in ["mp4", "direct", "hls", "mp4 (direct)", "hls (direct)"]:
                    direct_url = s.get("raw_url") or s.get("url", "")
                    provider_id = s.get("source", "unknown")
                    break
            
            # Fallback to first available direct stream if 720p not found
            if not direct_url:
                for s in sources_response["sources"]:
                    if s.get("type") in ["mp4", "direct", "hls", "mp4 (direct)", "hls (direct)"]:
                        direct_url = s.get("raw_url") or s.get("url", "")
                        provider_id = s.get("source", "unknown")
                        break
            
            # If still nothing, just grab the first one (though it might be iframe)
            if not direct_url:
                direct_url = sources_response["sources"][0].get("url", "")
                provider_id = sources_response["sources"][0].get("source", "unknown")
                
            print(f"Direct URL found: {direct_url[:50]}...")
            
            if direct_url and "tg-proxy" not in direct_url:
                success = await engine.process_episode(
                    episode_id=ep_id,
                    anilist_id=aid,
                    provider_id=provider_id,
                    episode_number=ep_num,
                    direct_video_url=direct_url
                )
                print(f"✅ Ingest Result {aid} Ep {ep_num}: {success}")
            else:
                print(f"⚠️ Invalid URL atau sudah Proxy: {direct_url[:50]}...")
        else:
            print(f"❌ Sumber mentah tidak ditemukan untuk {aid} Ep {ep_num}")

    if should_disconnect:
        await db.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest pending episodes")
    parser.add_argument("--limit", type=int, default=10, help="Max episodes to process")
    args = parser.parse_args()
    
    asyncio.run(ingest_pending(args.limit))