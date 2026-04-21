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
from services.providers import kuronime_provider
from services.pipeline import sync_anime_episodes

async def process_frieren():
    if not db.is_connected:
        await db.connect()
    
    print("🔍 Mencari 'Frieren' di Kuronime...")
    results = await kuronime_provider.search("frieren")
    
    target_slug = None
    for item in results:
        url = item.get('url', '')
        slug = url.strip('/').split('/')[-1]
        print(f"  - Ditemukan: {item.get('title')} -> Slug: {slug}")
        if "sousou-no-frieren" in slug.lower():
            target_slug = slug
            
    if target_slug:
        print(f"\n✅ Target Slug Ditemukan: {target_slug}")
        anilist_id = 154587
        
        # Masukkan ke mapping secara paksa (karena API Gemini sedang limit)
        print(f"💉 Menyuntikkan mapping Kuronime -> AniList {anilist_id} ke Database...")
        await db.execute(
            """
            INSERT INTO anime_mappings ("providerId", "providerSlug", "anilistId")
            VALUES ('kuronime', :slug, :aid)
            ON CONFLICT ("providerId", "providerSlug")
            DO UPDATE SET "anilistId" = EXCLUDED."anilistId"
            """,
            {"slug": target_slug, "aid": anilist_id},
        )
        
        # Jalankan Pipeline Sync untuk menarik semua episodenya!
        print(f"🔄 Menjalankan Pipeline Sync Episodes untuk Frieren (ID: {anilist_id})...")
        sync_result = await sync_anime_episodes(anilist_id)
        print(f"🎉 Hasil Sync: {sync_result}")
        
        # Cek database untuk memastikan episodenya masuk
        count = await db.fetch_val('SELECT COUNT(*) FROM episodes WHERE "anilistId" = :aid AND "providerId" = :pid', {"aid": anilist_id, "pid": "kuronime"})
        print(f"📊 Total Episode Frieren dari Kuronime di Database: {count} episode.")
        
    else:
        print("❌ Slug Frieren tidak ditemukan di hasil pencarian.")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(process_frieren())