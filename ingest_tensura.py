import asyncio
import os
import sys

# Setup path so apps/api modules can be imported correctly without namespace clashing
sys.path.insert(0, os.path.abspath("apps/api"))

from dotenv import load_dotenv
load_dotenv("apps/api/.env")
os.environ['PROXY_SECRET'] = "anime-pro-secure-2026"

from db.connection import database
from routes.stream_v2 import get_sources_v2
from services.ingestion.main import IngestionEngine

async def ingest():
    await database.connect()
    anilist_id = 108511
    ep_num = 1
    
    # Dapatkan sumber terbaru
    res = await get_sources_v2("That Time I Got Reincarnated as a Slime Season 2", ep_num, anilist_id)
    
    if not res['success'] or not res['sources']:
        print("Gagal mendapatkan sumber video")
        await database.disconnect()
        return
        
    # Cari yang 720p direct
    target_src = next((s for s in res['sources'] if s['quality'] == '720p' and s['type'] == 'direct'), None)
    if not target_src:
        # Fallback ke apa saja yang direct
        target_src = next((s for s in res['sources'] if s['type'] == 'direct'), None)
        
    if not target_src:
        print("Tidak ada URL direct yang tersedia.")
        await database.disconnect()
        return
        
    proxy_url = target_src['url']
    print(f"Menggunakan URL (Proxy terenkripsi): {proxy_url}")
    
    # Ambil ID episode dari DB
    row = await database.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": anilist_id, "ep": float(ep_num)})
    if not row:
        print("Episode tidak ditemukan di database.")
        await database.disconnect()
        return
        
    ep_id = row['id']
    
    # Trigger Ingestion Engine
    engine = IngestionEngine()
    print(f"\n🚀 Memulai Ingestion untuk Tensura S2 Ep 1 (720p) ke Telegram Swarm...")
    
    success = await engine.process_episode(
        episode_id=ep_id,
        anilist_id=anilist_id,
        provider_id="kuronime",
        episode_number=float(ep_num),
        direct_video_url=proxy_url
    )
    
    print(f"Hasil Ingestion: {'BERHASIL ✅' if success else 'GAGAL ❌'}")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(ingest())
