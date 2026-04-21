import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def fix_url():
    db = Database(db_url)
    await db.connect()
    
    rows = await db.fetch_all("""
        SELECT id, "episodeUrl" FROM episodes
        WHERE "episodeUrl" LIKE 'https://tg-proxy%https://tg-proxy%'
    """)
    for r in rows:
        url = r["episodeUrl"]
        # find the second https://
        idx = url.find("https://", 10)
        if idx != -1:
            new_url = url[idx:]
            await db.execute("""
                UPDATE episodes SET "episodeUrl" = :url WHERE id = :id
            """, {"url": new_url, "id": r["id"]})
            print(f"Fixed URL for id {r['id']}: {new_url}")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(fix_url())