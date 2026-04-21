import asyncio
import os
import sys
import json
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

load_dotenv("apps/api/.env", override=True)
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

from db.connection import database as db
from services.stream_cache import get_cached_stream

async def test_stream():
    if not db.is_connected:
        await db.connect()
        
    print("Fetching stream for Frieren (154587) Episode 1...")
    result = await get_cached_stream(154587, 1.0)
    print(json.dumps(result, indent=2))
    
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_stream())
