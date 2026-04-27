import asyncio
import sys

sys.path.append('.')
from db.connection import database
from services.stream_cache import get_cached_stream

async def test():
    await database.connect()
    res = await get_cached_stream(189046, 2.0)
    for s in res.get("sources", []):
        print(f"Provider: {s.get('provider')} | Quality: {s.get('quality')} | Type: {s.get('type')} | URL: {s.get('url')[:80]}")
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(test())