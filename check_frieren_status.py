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
    
    row = await db.fetch_one(
        """
        SELECT "episodeUrl", "updatedAt"
        FROM episodes 
        WHERE "anilistId" = 154587 AND "episodeNumber" = 1 AND "providerId" = 'kuronime'
        """
    )
    
    if row:
        url = row['episodeUrl']
        print(f"URL Saat Ini: {url}")
        if 'tg-proxy' in url or 'workers.dev' in url:
            print("✅ SUDAH DI TELEGRAM!")
        else:
            print("⏳ MASIH BELUM SELESAI (MASIH DIPROSES).")
    else:
        print("❌ Episode tidak ditemukan.")
        
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check())