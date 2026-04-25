import os
import asyncio
import httpx
import logging
import random
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# To use Telegram as a $0 cost unlimited object storage:
# 1. Create a Bot via BotFather and get BOT_TOKEN.
# 2. Get a CHAT_ID (can be a private channel or group) where the bot is admin.
# 3. Upload documents using sendDocument API endpoint.
# 4. Extract 'file_id' from the response.
# 5. The Cloudflare Worker proxy will stream the file by its 'file_id' via the getFile API.

# Pool of bots for load balancing and avoiding Rate Limits
# We dynamically load all TELEGRAM_BOT_TOKEN_* and pair them with available proxies
def _get_bot_pool():
    tokens = []
    proxies = []
    for k, v in os.environ.items():
        if k.startswith("TELEGRAM_BOT_TOKEN") and v:
            tokens.append(v)
        if k.startswith("TG_PROXY_BASE_URL") and v:
            proxies.append(v.rstrip("/"))
            
    # Default fallback proxy if none defined
    if not proxies:
        proxies = [""]
        
    pool = []
    for token in tokens:
        pool.append({
            "token": token,
            "proxy": random.choice(proxies)
        })
    return pool

class TelegramUploader:
    def __init__(self):
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.bot_pool = _get_bot_pool()
        self.client = None
        
        if not self.bot_pool:
            logger.warning("No valid bot tokens found in env. Uploader will fail.")
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID not set. Uploader will fail.")

    def _get_client(self):
        if self.client is None:
            limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
            timeout = httpx.Timeout(240.0, connect=60.0, pool=60.0)
            self.client = httpx.AsyncClient(limits=limits, timeout=timeout)
        return self.client

    async def close(self):
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    async def upload_file(self, file_path: str, max_retries: int = 5, bot: Optional[dict] = None) -> Optional[Dict]:
        """
        Uploads a single file to Telegram using a random bot from the pool.
        Returns a dict with url, message_id, bot_token if successful.
        """
        async def _debug(msg):
            try:
                from services.cache import client as redis_client
                from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
                import urllib.parse
                # Safely truncate message to avoid URL too long
                safe_msg = urllib.parse.quote(str(msg)[:200].replace('\n', ' '))
                await redis_client.get(f"{UPSTASH_REDIS_REST_URL}/lpush/debug_tg_log/{safe_msg}", headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
            except:
                pass
                
        if not self.bot_pool:
            return None
            
        client = self._get_client()
        bot = bot or random.choice(self.bot_pool)
        bot_token = bot["token"]
        proxy_url = bot["proxy"]

        file_size = os.path.getsize(file_path)
        endpoint = "sendVideo" if file_size > 10_000_000 else "sendDocument"
        url = f"https://api.telegram.org/bot{bot_token}/{endpoint}"
        
        await _debug(f"Uploading {os.path.basename(file_path)} using bot {bot_token[-4:]}...")
        
        for attempt in range(max_retries):
            try:
                await _debug(f"Attempt {attempt+1}: using shared connection pool to telegram API")
                with open(file_path, "rb") as f:
                    file_key = "video" if endpoint == "sendVideo" else "document"
                    files = {file_key: (os.path.basename(file_path), f)}
                    data = {"chat_id": self.chat_id}
                    
                    response = await client.post(url, data=data, files=files)
                    
                    if response.status_code == 200:
                        resp_json = response.json()
                        file_id = None
                        message_id = resp_json.get("result", {}).get("message_id")
                        if "document" in resp_json.get("result", {}):
                            file_id = resp_json["result"]["document"]["file_id"]
                        elif "video" in resp_json.get("result", {}):
                            file_id = resp_json["result"]["video"]["file_id"]
                            
                        if file_id:
                            final_url = f"{proxy_url}/{file_id}" if proxy_url else file_id
                            await asyncio.sleep(0.5)
                            return {
                                "url": final_url,
                                "message_id": message_id,
                                "bot_token": bot_token
                            }
                            
                    elif response.status_code == 429:
                        retry_after = response.json().get("parameters", {}).get("retry_after", 30)
                        wait = retry_after + random.uniform(5, 15)
                        await asyncio.sleep(wait)
                        
                        bot = random.choice(self.bot_pool)
                        bot_token = bot["token"]
                        url = f"https://api.telegram.org/bot{bot_token}/{endpoint}"
                        continue
                    else:
                        await _debug(f"Failed to upload {os.path.basename(file_path)}. HTTP {response.status_code}")
            except Exception as e:
                await _debug(f"Exception during Telegram upload (attempt {attempt+1}): {repr(e)}")
            
            wait = (2 ** attempt) * 5 + random.uniform(2, 5)
            await asyncio.sleep(wait)
            
            bot = random.choice(self.bot_pool)
            bot_token = bot["token"]
            url = f"https://api.telegram.org/bot{bot_token}/{endpoint}"

        return None

    async def _upstash_get(self, key: str):
        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token: return None
        try:
            res = await self.client.get(f"{url}/get/{key}", headers={"Authorization": f"Bearer {token}"})
            data = res.json()
            if data.get('result'):
                import json
                return json.loads(data['result'])
        except:
            pass
        return None

    async def _upstash_set(self, key: str, value: dict, ex: int = 86400):
        url = os.getenv("UPSTASH_REDIS_REST_URL")
        token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not url or not token: return
        try:
            import json
            payload = json.dumps(value)
            await self.client.post(f"{url}/set/{key}?EX={ex}", headers={"Authorization": f"Bearer {token}"}, data=payload)
        except:
            pass

    async def process_hls_playlist_parallel(self, m3u8_path: str, progress_key: Optional[str] = None, max_workers: int = 5) -> Optional[str]:
        """
        Reads a local .m3u8 playlist, uploads each .ts segment to Telegram IN PARALLEL using asyncio.Semaphore,
        and creates a new 'cloud' playlist where segments point to proxy URLs.
        Supports resumable uploads via Upstash Redis if progress_key is provided.
        Returns the path to the new .m3u8 playlist.
        """
        if not os.path.exists(m3u8_path):
            logger.error(f"Playlist {m3u8_path} not found.")
            return None

        hls_dir = os.path.dirname(m3u8_path)
        new_playlist_path = os.path.join(hls_dir, "cloud_index.m3u8")
        
        with open(m3u8_path, "r") as f:
            lines = f.readlines()

        segment_lines = [(i, line.strip()) for i, line in enumerate(lines) if line.strip() and not line.startswith("#")]
        
        existing_progress = {}
        if progress_key:
            cached = await self._upstash_get(progress_key)
            if cached and isinstance(cached, dict):
                existing_progress = cached
                logger.info(f"Found existing progress. Resuming {len(existing_progress)} segments.")

        uploaded_segments: Dict[int, str] = {}
        semaphore = asyncio.Semaphore(max_workers)

        async def _debug_log(msg):
            try:
                from services.cache import client
                from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
                import urllib.parse
                await client.get(f"{UPSTASH_REDIS_REST_URL}/lpush/debug_tg_log/{urllib.parse.quote(msg)}", headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
            except:
                pass
        
        await _debug_log(f"Starting parallel upload tasks for {len(segment_lines)} lines")

        # Do NOT select a single bot. We pass bot=None to upload_file
        # so it picks a random bot for EACH segment, enabling true Swarm Load Balancing.

        async def _upload_task(index: int, line: str):
            if str(index) in existing_progress:
                return index, existing_progress[str(index)]

            segment_path = os.path.join(hls_dir, line)
            if not os.path.exists(segment_path):
                logger.error(f"Segment missing locally: {os.path.basename(segment_path)}")
                return index, None
            
            await _debug_log(f"Task {index}: waiting for semaphore")
            async with semaphore:
                await _debug_log(f"Task {index}: acquired semaphore, uploading {segment_path}")
                # Force upload_file to pick a random bot
                file_res = await self.upload_file(segment_path, bot=None)
                await _debug_log(f"Task {index}: finished upload with result {bool(file_res)}")
                return index, file_res

        logger.info(f"Starting parallel upload of {len(segment_lines)} segments with {max_workers} workers (Swarm Load Balancing)...")
        
        tasks = [_upload_task(idx, line) for idx, line in segment_lines]
        
        # We will use as_completed to save incremental progress to Redis
        total_tasks = len(tasks)
        completed_tasks = 0
        
        await _debug_log(f"Entering as_completed loop with {total_tasks} tasks")
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                completed_tasks += 1
                
                if isinstance(result, tuple) and len(result) == 2:
                    idx, file_res = result
                    if file_res:
                        if isinstance(file_res, dict):
                            uploaded_segments[idx] = file_res["url"]
                            if progress_key:
                                existing_progress[str(idx)] = file_res
                        elif isinstance(file_res, str):
                            # Backwards compatibility
                            uploaded_segments[idx] = file_res
                            if progress_key:
                                existing_progress[str(idx)] = file_res
                                
                        # Log incremental progress to Upstash every 10 segments or at the end
                        if progress_key and (completed_tasks % 10 == 0 or completed_tasks == total_tasks):
                            try:
                                try:
                                    from db.cache import upstash_set
                                except ImportError:
                                    try:
                                        from services.cache import upstash_set
                                    except ImportError:
                                        from apps.api.services.cache import upstash_set
                                await upstash_set(progress_key, existing_progress, ex=86400)
                            except Exception as e:
                                pass
                    else:
                        logger.error(f"Failed to upload segment at line {idx}")
                else:
                    logger.error(f"Segment generated an exception: {result}")
            except Exception as exc:
                logger.error(f"Segment task failed with exception: {exc}")

        if len(uploaded_segments) < len(segment_lines):
            logger.error("Not all segments were uploaded successfully. Aborting playlist generation.")
            return None

        new_lines = []
        # Fallback proxy for backwards compatibility if string is just file_id
        fallback_proxy = os.getenv("TG_PROXY_BASE_URL", "")
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line and not line.startswith("#"):
                file_id = uploaded_segments.get(i)
                if file_id:
                    if file_id.startswith("http"):
                        new_url = file_id
                    else:
                        new_url = f"{fallback_proxy.rstrip('/')}/{file_id}"
                    new_lines.append(new_url)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        with open(new_playlist_path, "w") as f:
            f.write("\n".join(new_lines))
        
        logger.info(f"Successfully processed playlist to cloud: {new_playlist_path}")
        return new_playlist_path
