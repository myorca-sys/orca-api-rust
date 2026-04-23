import sys
import os
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import database
from services.pipeline import sync_anime_episodes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def mass_resync():
    await database.connect()
    try:
        # Get all anilistIds that have mappings, ordered by AniList popularity DESC
        # This ensures that the most popular animes get updated FIRST, instantly reflecting on the homepage!
        query = """
            SELECT m."anilistId"
            FROM anime_metadata m
            WHERE EXISTS (SELECT 1 FROM anime_mappings map WHERE map."anilistId" = m."anilistId")
            ORDER BY m.popularity DESC NULLS LAST
            LIMIT 500
        """
        rows = await database.fetch_all(query)
        anilist_ids = [row["anilistId"] for row in rows]
        
        logger.info(f"Found {len(anilist_ids)} animes to resync. Starting aggressive mass resync...")
        
        # Aggressive concurrency semaphore (20 concurrent)
        sem = asyncio.Semaphore(20)
        
        async def sync_one(aid: int):
            async with sem:
                logger.info(f"Resyncing anilistId: {aid}")
                try:
                    await sync_anime_episodes(aid)
                except Exception as e:
                    logger.error(f"Failed to resync {aid}: {e}")
                    
        # Larger chunks, minimal sleep
        chunk_size = 100
        for i in range(0, len(anilist_ids), chunk_size):
            chunk = anilist_ids[i:i+chunk_size]
            tasks = [sync_one(aid) for aid in chunk]
            await asyncio.gather(*tasks)
            # Ultra-minimal sleep
            await asyncio.sleep(0.05)
            
        logger.info("Mass resync completed successfully!")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(mass_resync())