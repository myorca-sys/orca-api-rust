import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from routes.stream_v2 import _scrape_kuronime
from db.connection import database

async def test():
    await database.connect()
    # Tensura S2 Ep 1, anilistId=108511
    # Kuronime slug for this is "tensei-shitara-slime-datta-ken-season-2"
    url = "https://kuronime.sbs/anime/tensei-shitara-slime-datta-ken-season-2/"
    res = await _scrape_kuronime("That Time I Got Reincarnated as a Slime Season 2", 1, url, 108511)
    import json
    print(json.dumps(res, indent=2))
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
