import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def check():
    db = Database(db_url)
    await db.connect()
    
    print("--- Tensura Ep 23 (101280) ---")
    rows = await db.fetch_all(
        """
        SELECT id, "providerId", "episodeUrl", "updatedAt"
        FROM episodes 
        WHERE "anilistId" = 101280 AND "episodeNumber" = 23
        """
    )
    for r in rows:
        print(dict(r))
        
    print("\n--- Frieren Ep 1 (154587) ---")
    rows = await db.fetch_all(
        """
        SELECT id, "providerId", "episodeUrl", "updatedAt"
        FROM episodes 
        WHERE "anilistId" = 154587 AND "episodeNumber" = 1
        """
    )
    for r in rows:
        print(dict(r))

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
