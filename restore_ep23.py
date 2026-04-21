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

async def run():
    await db.connect()
    
    await db.execute("""
        UPDATE episodes 
        SET "episodeUrl" = 'http://placeholder.com'
        WHERE id = 198101
    """)
    print("Restored Ep 23 URL to placeholder so it can be re-ingested.")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
