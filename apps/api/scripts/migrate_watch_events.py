import sys
import os
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.connection import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_watch_events():
    await database.connect()
    try:
        logger.info("Migrating legacy watch_events to watch_sessions...")
        
        # Insert into watch_sessions from watch_events
        # Group by user_id, anilistId, episodeNumber to create a session
        # We take the max timestamp_sec as watch_duration_sec, and min created_at as started_at
        
        query = """
            INSERT INTO watch_sessions (
                session_id, user_id, anilist_id, episode_number, 
                started_at, ended_at, watch_duration_sec, drop_timestamp_sec, completion_rate
            )
            SELECT 
                CONCAT(user_id, '_', "anilistId", '_', "episodeNumber") as session_id,
                user_id,
                "anilistId" as anilist_id,
                "episodeNumber" as episode_number,
                MIN(created_at) as started_at,
                MAX(created_at) as ended_at,
                MAX(COALESCE(timestamp_sec, 0)) as watch_duration_sec,
                MAX(COALESCE(timestamp_sec, 0)) as drop_timestamp_sec,
                MAX(CASE WHEN event_type = 'complete' THEN 1.0 ELSE 0.0 END) as completion_rate
            FROM watch_events
            GROUP BY user_id, "anilistId", "episodeNumber"
            ON CONFLICT (session_id) 
            DO UPDATE SET 
                watch_duration_sec = GREATEST(watch_sessions.watch_duration_sec, EXCLUDED.watch_duration_sec),
                drop_timestamp_sec = GREATEST(watch_sessions.drop_timestamp_sec, EXCLUDED.drop_timestamp_sec),
                completion_rate = GREATEST(watch_sessions.completion_rate, EXCLUDED.completion_rate),
                started_at = LEAST(watch_sessions.started_at, EXCLUDED.started_at),
                ended_at = GREATEST(watch_sessions.ended_at, EXCLUDED.ended_at);
        """
        
        await database.execute(query)
        logger.info("Migration of watch_events completed successfully!")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(migrate_watch_events())
