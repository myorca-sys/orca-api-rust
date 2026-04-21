import asyncio
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

from services.providers import kuronime_provider
import httpx

async def test():
    print("Fetching Frieren Ep 1 sources...")
    sources = await kuronime_provider.get_episode_sources("https://kuronime.sbs/nonton-sousou-no-frieren-episode-1/")
    kuro_url = None
    for s in sources:
        if s["provider"] == "KuroPlayer" and "1080p" in s["quality"]:
            kuro_url = s["url"]
            break
            
    if kuro_url:
        print(f"Got fresh URL: {kuro_url}")
        print("Curling it immediately with correct headers...")
        headers = {
            "Referer": "https://kuronime.sbs/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient() as client:
            res = await client.head(kuro_url, headers=headers)
            print(f"Status Code: {res.status_code}")
            if res.status_code == 404:
                print("Still returning 404!")
            else:
                print("IT WORKS WITH THE CORRECT UA!")
    else:
        print("No KuroPlayer 1080p source found.")

if __name__ == "__main__":
    asyncio.run(test())
