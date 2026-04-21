import asyncio
import sys
import os

# setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from services.providers import kuronime_provider

async def detail():
    url = "https://kuronime.sbs/anime/tensei-shitara-slime-datta-ken-season-2/"
    print(f"Fetching: {url}")
    res = await kuronime_provider.get_anime_detail(url)
    print("Episodes count:", len(res.get('episodes', [])))
    if res.get('episodes'):
        print("First episode:", res['episodes'][0])
        print("Last episode:", res['episodes'][-1])

if __name__ == "__main__":
    asyncio.run(detail())
