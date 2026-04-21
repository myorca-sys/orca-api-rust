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
        print("Running ffmpeg immediately...")
        # run ffmpeg to fetch 1 second
        cmd = f"ffmpeg -v error -headers 'Referer: https://kuronime.sbs/' -i '{kuro_url}' -t 1 -f null -"
        os.system(cmd)
        print("FFmpeg finished.")
    else:
        print("No KuroPlayer 1080p source found.")

if __name__ == "__main__":
    asyncio.run(test())
