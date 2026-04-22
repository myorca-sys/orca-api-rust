import sys
import os
import asyncio
import logging

# Ensure we can import from the api root
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.connection import database
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def aggregate_stats():
    """
    Aggregates raw watch_sessions into daily_anime_stats and user_watch_stats.
    This should be run via a cron job (e.g., hourly or daily).
    """
    await database.connect()
    try:
        logger.info("Starting data aggregation pipeline...")
        
        # 1. Aggregate Daily Anime Stats
        # We roll up watch sessions into daily stats. 
        # Using simple heuristics: 1 unique user = 10 popularity, 1 view = 2 trending
        logger.info("Aggregating daily anime stats...")
        query_anime_stats = """
            INSERT INTO daily_anime_stats ("anilistId", "date", "views", "popularity", "trending")
            SELECT 
                "anilist_id" as "anilistId", 
                DATE("started_at") as "date",
                COUNT(session_id) as "views",
                COUNT(DISTINCT "user_id") * 10 as "popularity",
                COUNT(session_id) * 2 as "trending"
            FROM watch_sessions
            GROUP BY "anilist_id", DATE("started_at")
            ON CONFLICT ("anilistId", "date") 
            DO UPDATE SET 
                views = EXCLUDED.views,
                popularity = EXCLUDED.popularity,
                trending = EXCLUDED.trending,
                "updatedAt" = NOW();
        """
        await database.execute(query_anime_stats)
        
        # 2. Update overall anime popularity & trending based on recent stats
        logger.info("Updating overall anime_metadata stats...")
        query_update_metadata = """
            UPDATE anime_metadata
            SET 
                popularity = COALESCE((SELECT SUM(popularity) FROM daily_anime_stats WHERE "anilistId" = anime_metadata."anilistId"), 0),
                trending = COALESCE((SELECT SUM(trending) FROM daily_anime_stats WHERE "anilistId" = anime_metadata."anilistId" AND date >= CURRENT_DATE - INTERVAL '7 days'), 0),
                "updatedAt" = NOW()
            WHERE EXISTS (SELECT 1 FROM daily_anime_stats WHERE "anilistId" = anime_metadata."anilistId");
        """
        await database.execute(query_update_metadata)

        # 3. Aggregate User Watch Stats
        logger.info("Aggregating user watch stats...")
        query_user_stats = """
            INSERT INTO user_watch_stats ("user_id", "total_anime_watched", "total_episodes_watched", "total_watch_time_sec")
            SELECT 
                "user_id",
                COUNT(DISTINCT "anilist_id") as "total_anime_watched",
                COUNT(DISTINCT CONCAT("anilist_id", '-', "episode_number")) as "total_episodes_watched",
                SUM("watch_duration_sec") as "total_watch_time_sec"
            FROM watch_sessions
            GROUP BY "user_id"
            ON CONFLICT ("user_id") 
            DO UPDATE SET 
                total_anime_watched = EXCLUDED.total_anime_watched,
                total_episodes_watched = EXCLUDED.total_episodes_watched,
                total_watch_time_sec = EXCLUDED.total_watch_time_sec,
                "updatedAt" = NOW();
        """
        await database.execute(query_user_stats)

        logger.info("Aggregation completed successfully!")
    except Exception as e:
        logger.error(f"Error during aggregation: {e}")
        raise
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(aggregate_stats())
