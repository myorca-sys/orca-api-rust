import os
import asyncio
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoFetcher:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.getenv("INGEST_TMP_DIR", "./tmp_ingest")
        os.makedirs(self.output_dir, exist_ok=True)

    async def fetch(self, url: str, output_filename: str, provider_id: str = "") -> Optional[str]:
        """
        Fetches a video from a direct URL (m3u8 or mp4) and saves it locally as an MP4.
        Uses ffmpeg for robust handling of streams asynchronously.
        """
        output_path = os.path.join(self.output_dir, output_filename)
        logger.info(f"Fetching video from {url} to {output_path}...")

        # If the file already exists, we skip to save bandwidth and time
        if os.path.exists(output_path):
            logger.info(f"File {output_path} already exists. Skipping fetch.")
            return output_path

        try:
            # --- ADVANCED HEADER SPOOFING ---
            import random

            # Mimic real browser behavior
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]

            # Generate a fake internal IP to try and confuse simple load balancers
            fake_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"

            h = {
                "User-Agent": random.choice(user_agents),
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://pixeldrain.com/",
                "Origin": "https://pixeldrain.com",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "video",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "X-Forwarded-For": fake_ip,
                "X-Real-IP": fake_ip
            }

            # Convert dict to FFmpeg header string
            headers_str = "".join([f"{k}: {v}\r\n" for k, v in h.items()])

            command = [
                "ffmpeg",
                "-y",
                "-headers", headers_str,
                "-i", url,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg failed with error: {stderr.decode()}")
                return None
                
            logger.info(f"Successfully fetched video to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Exception during fetching: {str(e)}")
            return None

if __name__ == "__main__":
    # Test execution
    # fetcher = VideoFetcher()
    # fetcher.fetch("https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8", "test_video.mp4")
    pass
