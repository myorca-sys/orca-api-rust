import asyncio
import httpx
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))
from services.providers import kuronime_provider

async def test():
    sources = await kuronime_provider.get_episode_sources("https://kuronime.sbs/nonton-tensei-shitara-slime-datta-ken-season-2-episode-1/")
    k_src = next((s for s in sources if s['provider'] == 'KuroPlayer'), None)
    if not k_src:
        print("No KuroPlayer source found")
        return
        
    url = k_src['url']
    if 'scraper-proxy-swarm' in url:
        print("Got proxy url, wait, we want the raw one. Let's find it in the payload.")
        import json
        import base64
        payload_b64 = url.split('/s/')[1].split('.')[0]
        payload_str = payload_b64 + '=' * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload_str))
        url = data['u']
        
    print(f"Raw URL: {url}")
    headers = {
        "Referer": "https://kuronime.sbs/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(verify=False) as client:
        res = await client.get(url, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text[:100]}")

if __name__ == "__main__":
    asyncio.run(test())
