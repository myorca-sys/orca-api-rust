import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from db.connection import database
from routes.stream_v2 import get_sources_v2

async def test():
    await database.connect()
    # Tensura S2 Ep 1, anilistId=108511
    res = await get_sources_v2("That Time I Got Reincarnated as a Slime Season 2", 1, 108511)
    import json
    print(json.dumps(res, indent=2))
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
