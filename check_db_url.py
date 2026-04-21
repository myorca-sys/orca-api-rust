import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))

from dotenv import load_dotenv
load_dotenv("apps/api/.env")

from db.connection import database

async def check():
    await database.connect()
    rows = await database.fetch_all('SELECT "providerId", "episodeUrl" FROM episodes WHERE "anilistId" = 108511 AND "episodeNumber" = 1')
    if rows:
        for r in rows:
            print(f"[{r['providerId']}] URL: {r['episodeUrl']}")
    else:
        print("Not found")
        
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
