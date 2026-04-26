import os
import httpx
import time
from services.config import QSTASH_TOKEN

class QStashPublisher:
    """Lightweight QStash REST publisher."""
    
    @staticmethod
    async def publish_sync_task(anilist_id: int):
        from services.cache import upstash_set
        lock_key = f"lock:sync:{anilist_id}"
        
        is_locked = await upstash_set(lock_key, "syncing", ex=300, nx=True)
        if not is_locked:
            print(f"[Queue] Sync for {anilist_id} already in progress.")
            return
            
        print(f"[Queue] Spawning background sync for {anilist_id} directly...")
        
        async def _sync_bg():
            try:
                from services.pipeline import sync_anime_episodes
                await sync_anime_episodes(anilist_id)
            except Exception as e:
                print(f"[Queue] Sync background task failed: {e}")
            finally:
                from services.cache import upstash_del
                await upstash_del(lock_key)
                
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_sync_bg())
        except RuntimeError:
            asyncio.run(_sync_bg())

    @staticmethod
    async def publish_ingest_task(episode_id: int, anilist_id: int, provider_id: str, episode_number: float, direct_url: str, delay: str = None):
        if not QSTASH_TOKEN:
            print(f"[QStash] Token missing, cannot queue ingest for Ep {episode_number}")
            return

        # --- DEDUPLICATION: Prevent redundant tasks using Redis lock ---
        from services.cache import upstash_set
        lock_key = f"ingest:{anilist_id}:{episode_number}"
        
        # nx=True means "only set if the key does not already exist" (Distributed Lock)
        # We lock for 30 minutes (1800s) to cover the typical ingestion duration
        is_locked = await upstash_set(lock_key, {
            "status": "processing",
            "started_at": int(time.time()),
            "provider": provider_id
        }, ex=1800, nx=True)
        
        if not is_locked:
            print(f"[QStash] Ingest already queued/in-progress for {anilist_id} Ep {episode_number}. Skipping deduplicate.")
            return
            
        target_url = os.getenv("API_PUBLIC_URL", "https://jonyyyyyyyu-anime-scraper-api.hf.space")
        target_url = f"{target_url.rstrip('/')}/api/v2/webhook/ingest"
        qstash_url = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")
        
        headers = {
            "Authorization": f"Bearer {QSTASH_TOKEN}",
            "Content-Type": "application/json",
            "Upstash-Retries": "5", 
        }
        if delay:
            headers["Upstash-Delay"] = delay
            
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    f"{qstash_url}/v2/publish/" + target_url,
                    headers=headers,
                    json={
                        "episode_id": episode_id,
                        "anilist_id": anilist_id,
                        "provider_id": provider_id,
                        "episode_number": episode_number,
                        "direct_url": direct_url
                    }
                )
                if res.status_code >= 400:
                    print(f"[QStash] Ingest Publish Failed: {res.status_code} - {res.text}")
                else:
                    delay_msg = f" with {delay} delay" if delay else ""
                    print(f"[QStash] Queued Ingestion for Ep {episode_number} successfully{delay_msg}.")
            except Exception as e:
                print(f"[QStash] Exception publishing ingest to QStash: {e}")

    @staticmethod
    def spawn_batch_worker(shard_id: int = 0, total_shards: int = 1):
        import asyncio
        print(f"[Queue] Spawning batch ingestion (Shard {shard_id}/{total_shards}) as native asyncio task...")
        
        async def _run():
            try:
                # Dynamically import to avoid circular dependencies
                import sys
                import os
                api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                if api_dir not in sys.path:
                    sys.path.insert(0, api_dir)
                
                from scripts.ingest_pending import ingest_pending
                await ingest_pending(5000, shard_id, total_shards)
            except Exception as e:
                print(f"[Queue] Native batch ingest error: {e}")
                
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_run())
        except RuntimeError:
            asyncio.run(_run())

    @staticmethod
    async def publish_ingest_batch_task():
        # Deduplication: Prevent redundant batch triggers within 15 minutes (900s)
        from services.cache import upstash_set
        lock_key = "lock:ingest_batch_trigger"
        
        is_locked = await upstash_set(lock_key, {
            "status": "queued",
            "started_at": int(time.time()),
        }, ex=900, nx=True)
        
        if not is_locked:
            print(f"[Queue] Batch ingest trigger already running. Skipping deduplicate.")
            return

        # Direct Background Execution (Bypasses QStash)
        # Because we are already running on the HF Space FastAPI, we can just spawn a task!
        print("[Queue] Spawning background batch ingestion directly...")
        QStashPublisher.spawn_batch_worker()

enqueue_sync = QStashPublisher.publish_sync_task
enqueue_ingest = QStashPublisher.publish_ingest_task
enqueue_ingest_batch = QStashPublisher.publish_ingest_batch_task