import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def map_tensura():
    db = Database(db_url)
    await db.connect()
    
    slug = "tensei-shitara-slime-datta-ken-season-2"
    anilist_id = 108511
    
    try:
        await db.execute("""
            INSERT INTO anime_mappings ("providerId", "providerSlug", "anilistId")
            VALUES ('kuronime', :slug, :anilist_id)
            ON CONFLICT ("providerId", "providerSlug")
            DO UPDATE SET "anilistId" = EXCLUDED."anilistId"
        """, {"slug": slug, "anilist_id": anilist_id})
        print(f"Mapped {slug} to {anilist_id} in anime_mappings")
    except Exception as e:
        print("Error mapping:", e)
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(map_tensura())
