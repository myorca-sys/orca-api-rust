import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from db.connection import database
from services.providers import kuronime_provider
from utils.extractor import UniversalExtractor

async def test_ep1():
    await database.connect()
    
    # Get Ep 1 URL for 108511 from Kuronime
    query = """
        SELECT "episodeUrl" 
        FROM episodes 
        WHERE "anilistId" = 108511 AND "episodeNumber" = 1.0 AND "providerId" = 'kuronime'
    """
    row = await database.fetch_one(query)
    
    if not row:
        print("Episode 1 not found in DB for kuronime.")
        await database.disconnect()
        return
        
    ep_url = row["episodeUrl"]
    print(f"Provider URL: {ep_url}")
    
    print("\n--- Extracting Sources ---")
    try:
        sources = await kuronime_provider.get_episode_sources(ep_url)
        print("Extracted Sources:", sources)
        
        # If there's an iframe or url, try to resolve raw video
        if sources:
            extractor = UniversalExtractor()
            target_url = sources[0]['url']
            print(f"\n--- Resolving Raw Video for: {target_url} ---")
            raw_url = await extractor.extract_raw_video(target_url)
            print("Raw Video URL:", raw_url)
            
            # Test CORS headers
            import httpx
            print("\n--- Testing CORS Headers ---")
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    res = await client.head(raw_url, headers={'Origin': 'http://localhost:3000'})
                    print(f"Status Code: {res.status_code}")
                    print("Headers:")
                    for k, v in res.headers.items():
                        if 'access-control' in k.lower():
                            print(f"  {k}: {v}")
                    if not any('access-control-allow-origin' in k.lower() for k in res.headers):
                        print("  [WARNING] No Access-Control-Allow-Origin header found!")
            except Exception as e:
                print("Error testing headers:", e)
    except Exception as e:
        print("Error extracting:", e)
        
    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(test_ep1())
