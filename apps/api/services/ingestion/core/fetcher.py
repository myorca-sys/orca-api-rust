import os
import asyncio
import logging
import random
import httpx
from typing import Optional
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Konfigurasi ────────────────────────────────────────────────────────────
CHUNK_WORKERS   = 4      # Koneksi paralel — sweet spot, tidak terlalu agresif
CHUNK_SIZE_MB   = 10     # Ukuran tiap chunk dalam MB
CONNECT_TIMEOUT = 15.0
READ_TIMEOUT    = 60.0
MAX_RETRIES     = 3

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def _make_headers(url: str) -> dict:
    parsed = urlparse(url)
    referer = f"https://{parsed.netloc}/"
    fake_ip = ".".join(str(random.randint(10, 254)) for _ in range(4))
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Origin": f"https://{parsed.netloc}",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "X-Forwarded-For": fake_ip,
        "X-Real-IP": fake_ip,
    }


async def _get_file_size(url: str, headers: dict) -> Optional[int]:
    """HEAD request untuk dapat Content-Length, fallback ke Range: bytes=0-0."""
    try:
        async with httpx.AsyncClient(timeout=CONNECT_TIMEOUT, follow_redirects=True, verify=False) as client:
            r = await client.head(url, headers=headers)
            if r.status_code == 200:
                cl = r.headers.get("content-length")
                if cl:
                    return int(cl)
            # Fallback: GET Range bytes=0-0 untuk dapat Content-Range header
            r2 = await client.get(url, headers={**headers, "Range": "bytes=0-0"})
            if r2.status_code == 206:
                cr = r2.headers.get("content-range", "")
                if "/" in cr:
                    total = cr.split("/")[-1]
                    if total != "*":
                        return int(total)
    except Exception as e:
        logger.warning(f"[Fetcher] Cannot get file size: {e}")
    return None


async def _download_chunk(
    url: str, headers: dict, start: int, end: int,
    chunk_index: int, output_path: str, semaphore: asyncio.Semaphore,
) -> bool:
    """Download satu chunk via Range request, tulis langsung ke posisi yang benar di file."""
    async with semaphore:
        range_header = {**headers, "Range": f"bytes={start}-{end}"}
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
                    follow_redirects=True,
                    verify=False
                ) as client:
                    async with client.stream("GET", url, headers=range_header) as r:
                        if r.status_code not in (200, 206):
                            logger.warning(f"[Fetcher] Chunk {chunk_index} HTTP {r.status_code}, retry {attempt+1}")
                            await asyncio.sleep(2 ** attempt)
                            continue
                        with open(output_path, "r+b") as f:
                            f.seek(start)
                            async for data in r.aiter_bytes(chunk_size=65536):
                                f.write(data)
                        logger.info(f"[Fetcher] Chunk {chunk_index} OK ({start}-{end})")
                        return True
            except Exception as e:
                logger.warning(f"[Fetcher] Chunk {chunk_index} error attempt {attempt+1}: {e}")
                await asyncio.sleep(2 ** attempt)
        logger.error(f"[Fetcher] Chunk {chunk_index} FAILED after {MAX_RETRIES} retries")
        return False


async def _parallel_download(url: str, output_path: str, file_size: int) -> bool:
    """Bagi file jadi chunks, download semua secara paralel."""
    chunk_bytes = CHUNK_SIZE_MB * 1024 * 1024
    headers = _make_headers(url)

    # Bagi file jadi chunks
    chunks = []
    offset, idx = 0, 0
    while offset < file_size:
        end = min(offset + chunk_bytes - 1, file_size - 1)
        chunks.append((offset, end, idx))
        offset = end + 1
        idx += 1

    logger.info(f"[Fetcher] {len(chunks)} chunks x {CHUNK_SIZE_MB}MB | {CHUNK_WORKERS} workers paralel")

    part_file = f"{output_path}.part"

    # Pre-allocate file dengan ukuran penuh agar bisa tulis di posisi manapun
    with open(part_file, "wb") as f:
        f.seek(file_size - 1)
        f.write(b"\x00")

    semaphore = asyncio.Semaphore(CHUNK_WORKERS)
    tasks = [
        _download_chunk(url, headers, start, end, i, part_file, semaphore)
        for start, end, i in chunks
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed = sum(1 for r in results if r is not True)
    if failed > 0:
        logger.error(f"[Fetcher] {failed}/{len(chunks)} chunks gagal")
        if os.path.exists(part_file):
            os.remove(part_file)
        return False

    # Rename .part to final output_path if successful
    if os.path.exists(output_path):
        os.remove(output_path)
    os.rename(part_file, output_path)

    logger.info(f"[Fetcher] Semua {len(chunks)} chunks berhasil diunduh")
    return True


async def _single_stream_download(url: str, output_path: str) -> bool:
    """Fallback: FFmpeg single stream untuk HLS atau server yang tidak support Range."""
    logger.info(f"[Fetcher] Menggunakan FFmpeg single stream")
    headers = _make_headers(url)
    headers_str = "".join([f"{k}: {v}\r\n" for k, v in headers.items()])
    command = [
        "ffmpeg", "-y",
        "-headers", headers_str,
        "-i", url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        output_path,
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        logger.error(f"[Fetcher] FFmpeg gagal: {stderr.decode()[-400:]}")
        return False
    return True


class VideoFetcher:
    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.getenv("INGEST_TMP_DIR", "./tmp_ingest")
        os.makedirs(self.output_dir, exist_ok=True)

    async def fetch(self, url: str, output_filename: str, provider_id: str = "") -> Optional[str]:
        """
        Download video dari URL ke disk.

        Strategy otomatis:
        1. HLS (.m3u8)          → FFmpeg langsung (tidak bisa di-chunk)
        2. MP4 + Range support  → Parallel chunk download (4 koneksi paralel)
        3. MP4 + no Range       → FFmpeg single stream fallback
        """
        output_path = os.path.join(self.output_dir, output_filename)
        logger.info(f"[Fetcher] Target: {url[:80]}...")

        headers = _make_headers(url)
        
        # Determine file size first to verify existing file
        file_size = None
        if not ".m3u8" in url.lower():
            file_size = await _get_file_size(url, headers)

        # Skip kalau file sudah ada dan ukurannya sama persis (atau m3u8 yang sulit dicek ukurannya tapi filenya lumayan besar)
        if os.path.exists(output_path):
            local_size = os.path.getsize(output_path)
            if file_size and local_size == file_size:
                logger.info(f"[Fetcher] Sudah ada dan ukuran cocok ({local_size} bytes), skip download: {output_path}")
                return output_path
            elif not file_size and local_size > 1024 * 1024: # Asumsi > 1MB cukup untuk m3u8 hasil ffmpeg
                logger.info(f"[Fetcher] Sudah ada (HLS/Unknown Size) > 1MB, skip download: {output_path}")
                return output_path
            else:
                logger.info(f"[Fetcher] File corrupt/incomplete (Local: {local_size}, Server: {file_size}). Menghapus file lama...")
                os.remove(output_path)

        # HLS → langsung FFmpeg
        if ".m3u8" in url.lower():
            success = await _single_stream_download(url, output_path)
            return output_path if success else None

        # MP4 → coba parallel download
        headers = _make_headers(url)
        file_size = await _get_file_size(url, headers)

        if file_size and file_size > 0:
            logger.info(f"[Fetcher] Ukuran file: {file_size/1024/1024:.1f}MB → parallel download")
            success = await _parallel_download(url, output_path, file_size)
        else:
            # Server tidak support Range atau tidak return size
            logger.info(f"[Fetcher] Ukuran tidak diketahui → FFmpeg fallback")
            success = await _single_stream_download(url, output_path)

        if not success:
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

        actual = os.path.getsize(output_path)
        logger.info(f"[Fetcher] Selesai: {actual/1024/1024:.1f}MB → {output_path}")
        return output_path
