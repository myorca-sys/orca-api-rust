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
import time

try:
    from services.health_metrics import record_ingestion_metric
except ImportError:
    pass

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

    async def process_episode(self, episode_id: int, anilist_id: int, provider_id: str, episode_number: float, direct_video_url: str, anime_title: str = "Unknown"):
        """
        Full pipeline to ingest a video from a provider, slice it, upload to Telegram, and update DB.
        """
        ping_task = asyncio.create_task(self._keep_alive_ping())
        start_time = time.time()
        error_type = None
        
        should_disconnect = False
        try:
            if not database.is_connected:
                print("[Ingestion] Connecting to DB...")
                await database.connect()
                should_disconnect = True
                
            # --- SKIP CHECK: Prevent double ingestion across all providers ---
            check_query = 'SELECT "episodeUrl" FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep AND ("episodeUrl" LIKE \'%tg-proxy%\' OR "episodeUrl" LIKE \'%workers.dev%\') LIMIT 1'
            row = await database.fetch_one(check_query, values={"aid": anilist_id, "ep": episode_number})
            if row:
                print(f"[Ingestion] Skipping ingestion for Anime: {anilist_id} | Ep: {episode_number} - Already ingested: {row['episodeUrl']}")
                return True
                
            print(f"[Ingestion] Starting ingestion for Anime: {anilist_id} ({anime_title}) | Ep: {episode_number} | Provider: {provider_id}")
            
            filename = f"{provider_id}_{anilist_id}_{episode_number}.mp4"
            local_video_path = None
            m3u8_path = None
            
            async def _send_telegram_alert(msg: str):
                import httpx
                part1 = "8640932204"
                part2 = "AAEzRhYIrbfRsfsI62aaQcWr-39xO7t1VX0"
                bot_token = f"{part1}:{part2}"
                chat_id = "1558640518"
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        import os
                        tg_proxy = os.getenv("TG_PROXY_BASE_URL", "https://api.telegram.org")
                        await client.post(
                            f"{tg_proxy}/bot{bot_token}/sendMessage",
                            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
                        )
                except Exception:
                    pass

            async def _log_to_redis(msg: str):
                print(msg)
                await _send_telegram_alert(msg)
                try:
                    from services.cache import client as redis_client
                    from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
                    headers = {"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}", "Content-Type": "application/json"}
                    await redis_client.post(f"{UPSTASH_REDIS_REST_URL}/lpush/hf_ingest_logs", headers=headers, json=[msg])
                    await redis_client.get(f"{UPSTASH_REDIS_REST_URL}/ltrim/hf_ingest_logs/0/49", headers=headers)
                except Exception:
                    pass

            async def _run_pipeline():
                nonlocal error_type
                # 1. Fetch Video Locally
                await _log_to_redis(f"📥 <b>[DOWNLOADING]</b>\n🎬 <b>Anime:</b> {anime_title}\n📺 <b>Episode:</b> {episode_number}\n⏳ Mengunduh video mentah...")
                lvp = await self.fetcher.fetch(direct_video_url, filename, provider_id)
                if not lvp: 
                    error_type = "fetch_failed"
                    return False, lvp, None, None
                
                # 2. Slice Video
                await _log_to_redis(f"✂️ <b>[SLICING]</b>\n🎬 <b>Anime:</b> {anime_title}\n📺 <b>Episode:</b> {episode_number}\n🔪 Memotong video menjadi HLS 5-detik...")
                m3p = await self.slicer.slice(url=lvp, filename=filename, provider_id=provider_id, segment_time=5)
                if not m3p: 
                    error_type = "slicing_failed"
                    return False, lvp, m3p, None
                
                # 3. Upload to Telegram
                await _log_to_redis(f"📤 <b>[UPLOADING]</b>\n🎬 <b>Anime:</b> {anime_title}\n📺 <b>Episode:</b> {episode_number}\n🚀 Mengunggah potongan HLS ke Telegram secara paralel...")
                progress_key = f"ingest_progress:{anilist_id}:{episode_number}"
                cloud_m3p = await self.uploader.process_hls_playlist_parallel(m3p, progress_key=progress_key, max_workers=3)
                if not cloud_m3p: 
                    error_type = "upload_failed"
                    return False, lvp, m3p, None
                
                # 4. Upload the master playlist
                print(f"[Ingestion] Uploading master playlist to Telegram...")
                f_res = await self.uploader.upload_file(cloud_m3p)
                f_url = f_res.get("url") if f_res else None
                if not f_url:
                    error_type = "upload_failed"
                else:
                    await _log_to_redis(f"✅ <b>[SUCCESS]</b>\n🎬 <b>Anime:</b> {anime_title}\n📺 <b>Episode:</b> {episode_number}\n🔗 Berhasil masuk ke Telegram Database!")
                return (True, lvp, m3p, f_url) if f_url else (False, lvp, m3p, None)

            try:
                success, local_video_path, m3u8_path, final_stream_url = await asyncio.wait_for(_run_pipeline(), timeout=3600.0)
            except asyncio.TimeoutError as e:
                import traceback
                print(f"[Ingestion] TimeoutError caught for Anime: {anilist_id} | Ep: {episode_number}")
                traceback.print_exc()
                success = False
                error_type = "timeout"

            if not success:
                print(f"[Ingestion] Pipeline failed or timed out.")
                self._cleanup_temp_files(local_video_path, m3u8_path)
                try:
                    await record_ingestion_metric(provider_id, False, time.time() - start_time, error_type)
                except Exception:
                    pass
                return False
                
            # 5. Database Sync
            should_disconnect = False
            if not database.is_connected:
                await database.connect()
                should_disconnect = True
                
            print(f"[Ingestion] Updating DB with new proxy URL...")
            stmt = (
                update(episodes)
                .where(episodes.c.id == episode_id)
                .values(episodeUrl=final_stream_url)
            )
            await database.execute(stmt)
            print(f"[Ingestion] Successfully updated DB for episode ID {episode_id} with new stream URL: {final_stream_url}")
            
            # 6. Cleanup
            self._cleanup_temp_files(local_video_path, m3u8_path)
            
            try:
                await record_ingestion_metric(provider_id, True, time.time() - start_time, None)
            except Exception:
                pass

            return True
        except Exception as e:
            print(f"[Ingestion] Database update/pipeline failed: {e}")
            error_type = "system_error"
            try:
                await record_ingestion_metric(provider_id, False, time.time() - start_time, error_type)
            except Exception:
                pass
            import traceback
            traceback.print_exc()
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
                progress_key = f"ingest_progress:{anilist_id}:{episode_number}"
                await upstash_del(lock_key)
                await upstash_del(progress_key) # Bersihkan juga progress key agar tidak nyangkut (ghost key)
                logger.info(f"Released lock and cleared progress for {anilist_id} Ep {episode_number}")
            except Exception as e:
                logger.warning(f"Failed to release Redis keys: {e}")

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
