import asyncio
import os
from dotenv import load_dotenv

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from databases import Database

async def bump():
    db = Database(db_url)
    await db.connect()
    
    # Update the timestamp so it becomes the first in the queue for the HF batch worker
    await db.execute("""
        UPDATE episodes 
        SET "updatedAt" = NOW() + interval '1 day'
        WHERE "anilistId" = 154587 AND "episodeNumber" = 1 AND "providerId" = 'kuronime'
    """)
    print("Bumped Frieren Ep 1 to the top of the queue!")
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(bump())
