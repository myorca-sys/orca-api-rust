import asyncio
import sys
import os
import httpx
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from db.connection import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def sync_jikan():
    await database.connect()
    try:
        # Get canonical animes with mal_id, ordered by popularity
        query = """
            SELECT c.id, c.mal_id 
            FROM canonical_anime c
            JOIN anime_metadata m ON m."anilistId" = c.anilist_id
            WHERE c.mal_id IS NOT NULL
            ORDER BY m.popularity DESC NULLS LAST
        """
        rows = await database.fetch_all(query)
        logger.info(f"Found {len(rows)} canonical animes with mal_id. Starting Jikan sync...")
        
        async with httpx.AsyncClient() as client:
            for row in rows:
                cid = row["id"]
                mal_id = row["mal_id"]
                
                try:
                    # Jikan API rate limit is 3 requests per second, 60 per minute.
                    # We sleep 1 second per request to be extremely safe.
                    res = await client.get(f"https://api.jikan.moe/v4/anime/{mal_id}/statistics", timeout=10.0)
                    if res.status_code == 200:
                        data = res.json().get("data", {})
                        watching = data.get("watching")
                        completed = data.get("completed")
                        dropped = data.get("dropped")
                        
                        from services.reconciler import reconciler
                        
                        if watching is not None:
                            await reconciler.record_metadata_source(
                                canonical_id=cid,
                                source_name="jikan_api",
                                field_name="watching",
                                raw_value=str(watching),
                                confidence=0.9
                            )
                        if completed is not None:
                            await reconciler.record_metadata_source(
                                canonical_id=cid,
                                source_name="jikan_api",
                                field_name="completed",
                                raw_value=str(completed),
                                confidence=0.9
                            )
                        if dropped is not None:
                            await reconciler.record_metadata_source(
                                canonical_id=cid,
                                source_name="jikan_api",
                                field_name="dropped",
                                raw_value=str(dropped),
                                confidence=0.9
                            )
                        logger.info(f"Synced Jikan stats for mal_id={mal_id} (watching: {watching}, completed: {completed})")
                    elif res.status_code == 429:
                        logger.warning("Jikan API rate limit hit! Sleeping for 10 seconds...")
                        await asyncio.sleep(10)
                    else:
                        logger.error(f"Failed to fetch Jikan stats for mal_id={mal_id}: HTTP {res.status_code}")
                except Exception as e:
                    logger.error(f"Error for mal_id={mal_id}: {e}")
                
                await asyncio.sleep(1.1)  # Respect rate limit
                
        logger.info("Jikan sync completed.")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(sync_jikan())
