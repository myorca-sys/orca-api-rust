import asyncio
import sys
from urllib.parse import urlparse

url = "https://a6.mp4upload.com:183/d/w2xxvp7uz3b4quuod2quypcdj4glhyd5lvejmknjjnuvujhada5hwpjnkg4xgjcbm4jpq5kg/video.mp4"
referer = f"https://{urlparse(url).netloc}/"

async def test():
    print(f"Testing URL: {url}")
    print(f"Referer: {referer}")
    command = [
        "ffmpeg", "-v", "warning",
        "-headers", f"Referer: {referer}\r\n",
        "-i", url,
        "-t", "5",
        "-f", "null", "-"
    ]
    process = await asyncio.create_subprocess_exec(*command)
    await process.communicate()
    print(f"Exit code: {process.returncode}")

asyncio.run(test())
