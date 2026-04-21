import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from services.pipeline import sync_anime_episodes
from db.connection import database

async def run():
    print("Connecting to DB...")
    await database.connect()
    
    print("Syncing 108511 (Tensura S2)...")
    await sync_anime_episodes(108511)
    
    print("Done")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(run())
