import os
import asyncio
import logging
from typing import Optional, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoSlicer:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.getenv("INGEST_HLS_TMP_DIR", "./tmp_ingest/hls")
        os.makedirs(self.output_dir, exist_ok=True)

    async def slice(self, url: str, filename: str, provider_id: str = "", segment_time: int = 12) -> Optional[str]:
        base_name = os.path.splitext(filename)[0]
        hls_dir = os.path.join(self.output_dir, base_name)
        if os.path.exists(hls_dir):
            import shutil
            shutil.rmtree(hls_dir)
        os.makedirs(hls_dir, exist_ok=True)

        master_playlist = os.path.join(hls_dir, "index.m3u8")
        logger.info(f"🚀 [Ep 23 TEST] Slicing with Subtitle Mapping from {url}...")

        try:
            # Perintah FFmpeg sakti: Copy Video & Audio (Cepat), tapi Map Subtitle ke format HLS
            command = [
                "ffmpeg", "-y",
                "-headers", "Referer: https://pixeldrain.com/\r\n",
                "-i", url,
                "-map", "0:v:0", "-map", "0:a:0", "-map", "0:s:0?", # Ambil Video, Audio, dan Teks pertama
                "-c:v", "copy", "-c:a", "copy", "-c:s", "webvtt", # WebVTT adalah standar HLS
                "-f", "hls", "-hls_time", str(segment_time), "-hls_list_size", "0",
                "-hls_segment_filename", os.path.join(hls_dir, "segment_%04d.ts"),
                master_playlist
            ]
            
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if os.path.exists(master_playlist) and os.path.getsize(master_playlist) > 0:
                logger.info(f"✅ Berhasil memotong Ep 23 dengan Subtitle!")
                return master_playlist
            
            logger.error(f"FFmpeg Error: {stderr.decode()}")
            return None
        except Exception as e:
            logger.error(f"Slicer Exception: {e}")
            return None
