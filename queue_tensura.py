import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from dotenv import load_dotenv
load_dotenv("apps/api/.env")
os.environ['PROXY_SECRET'] = "anime-pro-secure-2026"

from db.connection import database
from services.queue import enqueue_ingest
from services.providers import kuronime_provider
from utils.extractor import UniversalExtractor
from utils.signed_url import sign_stream_url

async def queue_tensura():
    await database.connect()
    anilist_id = 108511
    ep_num = 1.0
    
    print("Mendapatkan URL langsung dari Kuronime untuk Ep 1...")
    ep_url = "https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/"
    sources = await kuronime_provider.get_episode_sources(ep_url)
    
    target_src = next((s for s in sources if s['provider'] == 'Mp4upload' and s['quality'] == '720p'), None)
    if not target_src:
        target_src = next((s for s in sources if s['provider'] == 'Mp4upload'), None)
        
    if not target_src:
        print("Tidak ada URL Mp4upload yang tersedia.")
        await database.disconnect()
        return
        
    # Extract
    ex = UniversalExtractor()
    raw_url = await ex.extract_raw_video(target_src['url'])
    
    # Wrap in proxy
    proxy_url = sign_stream_url(raw_url, "mp4upload", "720p")
    print(f"Proxy URL terenkripsi: {proxy_url}")
    
    # Ambil ID episode dari DB
    row = await database.fetch_one('SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1', values={"aid": anilist_id, "ep": ep_num})
    if not row:
        print("Episode tidak ditemukan di database.")
        await database.disconnect()
        return
        
    ep_id = row['id']
    
    print(f"\n🚀 Mendorong Antrean Ingestion untuk Tensura S2 Ep {ep_num} (720p) ke Hugging Face (via QStash)...")
    
    try:
        await enqueue_ingest(
            episode_id=ep_id,
            anilist_id=anilist_id,
            provider_id="kuronime",
            episode_number=ep_num,
            direct_url=proxy_url,
            delay="0s" # Langsung dieksekusi
        )
        print(f"✅ Ep {ep_num} sukses didorong ke antrean QStash/Hugging Face!")
        print("Bot Telegram Swarm Storage akan memprosesnya secara paralel di latar belakang.")
    except Exception as e:
        print(f"❌ Gagal antre Ep {ep_num}: {e}")

    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(queue_tensura())
