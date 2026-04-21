import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from db.connection import database
from services.stream_cache import stream_cache

async def test():
    await database.connect()
    
    ep_url = "https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/"
    
    print("Invalidating old cache...")
    await stream_cache.invalidate(ep_url)
    
    print("Fetching stream using stream_cache (simulating frontend)...")
    res = await stream_cache.get_stream(ep_url, "kuronime")
    
    import json
    print(json.dumps(res, indent=2))
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
