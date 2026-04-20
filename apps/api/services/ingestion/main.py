import os
import sys
import logging
import asyncio
import shutil
import httpx
from typing import Optional

# Add the root directory to Python path if running independently
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .core.fetcher import VideoFetcher
from .core.slicer import VideoSlicer
from .uploader.telegram import TelegramUploader
try:
    from db.connection import database
    from db.models import episodes
except ImportError:
    from apps.api.db.connection import database
    from apps.api.db.models import episodes
from sqlalchemy import update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IngestionEngine:
    def __init__(self):
        self.fetcher = VideoFetcher()
        self.slicer = VideoSlicer()
        self.uploader = TelegramUploader()

    async def _keep_alive_ping(self):
        """Pings the healthz endpoint every 15 seconds to prevent HF Space sleep during ingestion."""
        api_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space").rstrip("/")
        health_url = f"{api_url}/healthz"
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    await client.head(health_url, timeout=5.0)
                    logger.info("[Keep-Alive] Pinged HF Space health endpoint to prevent sleep.")
                except Exception as e:
                    logger.warning(f"[Keep-Alive] Ping failed: {e}")
                await asyncio.sleep(15)

    async def process_episode(self, episode_id: int, anilist_id: int, provider_id: str, episode_number: float, direct_video_url: str):
        """
        Full pipeline to ingest a video from a provider, slice it, upload to Telegram, and update DB.
        """
        ping_task = asyncio.create_task(self._keep_alive_ping())
        
        should_disconnect = False
        try:
            if not database.is_connected:
                await database.connect()
                should_disconnect = True
                
            # --- SKIP CHECK: Prevent double ingestion ---
            check_query = 'SELECT "episodeUrl" FROM episodes WHERE id = :id'
            row = await database.fetch_one(check_query, values={"id": episode_id})
            if row and ("tg-proxy" in row["episodeUrl"] or "workers.dev" in row["episodeUrl"]):
                logger.info(f"Skipping ingestion for Anime: {anilist_id} | Ep: {episode_number} - Already ingested: {row['episodeUrl']}")
                return True
                
            logger.info(f"Starting ingestion for Anime: {anilist_id} | Ep: {episode_number} | Provider: {provider_id}")
            
            filename = f"{provider_id}_{anilist_id}_{episode_number}.mp4"
            
            # 1 & 2. Streaming Slice (On-the-fly from Provider URL to HLS)
            m3u8_path = await self.slicer.slice(url=direct_video_url, filename=filename, provider_id=provider_id, segment_time=12)
            if not m3u8_path:
                logger.error("Failed to slice video on-the-fly.")
                return False

            # 3. Upload to Telegram (Parallel Swarm)
            progress_key = f"ingest_progress:{anilist_id}:{episode_number}"
            cloud_m3u8_path = await self.uploader.process_hls_playlist_parallel(m3u8_path, progress_key=progress_key, max_workers=3)
            if not cloud_m3u8_path:
                logger.error("Failed to upload segments to Telegram.")
                return False
                
            # 4. Upload the master playlist itself to Telegram or use it directly
            playlist_file_id = await self.uploader.upload_file(cloud_m3u8_path)
            if not playlist_file_id:
                logger.error("Failed to upload master playlist to Telegram.")
                return False
                
            # 5. Database Sync (Asynchronous)
            proxy_url = os.getenv("TG_PROXY_BASE_URL")
            if not proxy_url:
                raise ValueError("TG_PROXY_BASE_URL wajib di-set")
            final_stream_url = f"{proxy_url.rstrip('/')}/{playlist_file_id}"
            
            should_disconnect = False
            if not database.is_connected:
                await database.connect()
                should_disconnect = True
                
            stmt = (
                update(episodes)
                .where(episodes.c.id == episode_id)
                .values(episodeUrl=final_stream_url)
            )
            await database.execute(stmt)
            logger.info(f"Successfully updated DB for episode ID {episode_id} with new stream URL: {final_stream_url}")
            
            # 6. Cleanup (After successful sync)
            self._cleanup_temp_files(None, m3u8_path)
            
            return True
        except Exception as e:
            logger.error(f"Database update failed: {e}")
            return False
        finally:
            if ping_task and not ping_task.done():
                ping_task.cancel()
            try:
                if 'should_disconnect' in locals() and should_disconnect:
                    await database.disconnect()
            except Exception as e:
                logger.warning(f"Failed to disconnect DB: {e}")
                
            try:
                from services.cache import upstash_del
                lock_key = f"ingest:{anilist_id}:{episode_number}"
                await upstash_del(lock_key)
                logger.info(f"Released lock for {lock_key}")
            except Exception as e:
                logger.warning(f"Failed to release Redis lock: {e}")

    def _cleanup_temp_files(self, mp4_path: str, m3u8_path: str):
        """Removes local temporary files to save disk space."""
        try:
            if mp4_path and os.path.exists(mp4_path):
                os.remove(mp4_path)
                logger.info(f"Removed raw MP4: {mp4_path}")
            
            if m3u8_path:
                hls_dir = os.path.dirname(m3u8_path)
                if os.path.exists(hls_dir):
                    shutil.rmtree(hls_dir)
                    logger.info(f"Removed HLS directory: {hls_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp files: {e}")

if __name__ == "__main__":
    async def run_test():
        engine = IngestionEngine()
        
        from db.connection import database
        await database.connect()
        row = await database.fetch_one('SELECT id FROM episodes WHERE "anilistId" = 101280 AND "episodeNumber" = 1.0 LIMIT 1')
        if row:
            ep_id = row['id']
            # Using the 720p URL confirmed by user
            await engine.process_episode(
                episode_id=ep_id,
                anilist_id=101280,
                provider_id="kuronime",
                episode_number=1.0,
                direct_video_url="https://a6.mp4upload.com:183/d/w2xqdoxpz3b4quuoxkqeuzarixrlhhgqlfxlszjp7hwtqjiuoeqjzjfvnoi2bcpcv4wh6aem/video.mp4"
            )
        await database.disconnect()
        
    asyncio.run(run_test())
