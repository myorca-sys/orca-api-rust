import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def check_db():
    db = Database(db_url)
    await db.connect()
    
    print("\n--- One Piece (Anilist 101280 / 21) Mappings ---")
    query_op = """
        SELECT "anilistId", "providerId", "providerSlug"
        FROM anime_mappings
        WHERE "anilistId" IN (101280, 21)
    """
    rows_op = await db.fetch_all(query_op)
    for row in rows_op:
        print(f"[{row['anilistId']} - {row['providerId']}] Slug: {row['providerSlug']}")

    print("\n--- Dan Da Dan Mappings ---")
    query_ddd = """
        SELECT "anilistId", "providerId", "providerSlug"
        FROM anime_mappings
        WHERE "anilistId" IN (171018, 162804)
    """
    rows_ddd = await db.fetch_all(query_ddd)
    for row in rows_ddd:
        print(f"[{row['anilistId']} - {row['providerId']}] Slug: {row['providerSlug']}")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_db())