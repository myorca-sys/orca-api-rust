import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))
from utils.extractor import UniversalExtractor

async def test():
    urls = [
        "https://vidhidevip.com/v/ra8y6cus5rm0", # filelions / vidhide
        "https://pixeldrain.com/u/rxWH6FJ6?embed",
        "https://krakenfiles.com/embed-video/tro1PixDLt",
        "https://www.mp4upload.com/embed-wzbiavr1xg91.html"
    ]
    ex = UniversalExtractor()
    for u in urls:
        print(f"\n--- Extracting {u} ---")
        try:
            res = await ex.extract_raw_video(u)
            print(f"Result: {res}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
