import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def check_kuronime_mapped():
    db = Database(db_url)
    await db.connect()
    
    query = """
        SELECT m."anilistId", m."providerSlug", meta."cleanTitle"
        FROM anime_mappings m
        JOIN anime_metadata meta ON m."anilistId" = meta."anilistId"
        WHERE m."providerId" = 'kuronime'
        ORDER BY m."updatedAt" DESC
        LIMIT 20
    """
    rows = await db.fetch_all(query)
    
    print("=== DAFTAR ANIME KURONIME YANG SUDAH TER-MAPPING ===")
    if not rows:
        print("Belum ada anime dari Kuronime yang berhasil di-mapping.")
    else:
        for row in rows:
            print(f"✅ {row['cleanTitle']} (AniList ID: {row['anilistId']}) -> Slug: {row['providerSlug']}")
            
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_kuronime_mapped())