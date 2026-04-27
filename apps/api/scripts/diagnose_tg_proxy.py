import asyncio
import databases
import os
import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

async def check_episode(client, row):
    url = row["episodeUrl"]
    anime_id = row["anilistId"]
    ep_num = row["episodeNumber"]
    provider = row["providerId"]
    
    result = {
        "anime_id": anime_id,
        "ep_num": ep_num,
        "provider": provider,
        "url": url,
        "status": "Unknown",
        "duration": 0,
        "issue": None
    }
    
    try:
        # Fetch the M3U8 playlist
        resp = await client.get(url, timeout=10.0)
        
        if resp.status_code != 200:
            result["issue"] = f"HTTP {resp.status_code}"
            result["status"] = "Failed (M3U8 unreachable)"
            return result
            
        text = resp.text
        if "#EXTM3U" not in text:
            result["issue"] = "Not a valid M3U8 file"
            result["status"] = "Failed (Invalid format)"
            return result
            
        # Parse duration
        duration = 0.0
        lines = text.splitlines()
        first_segment = None
        
        for line in lines:
            if line.startswith("#EXTINF:"):
                try:
                    dur_str = line.split(":")[1].split(",")[0]
                    duration += float(dur_str)
                except:
                    pass
            elif line and not line.startswith("#"):
                if not first_segment:
                    first_segment = line
                    
        result["duration"] = duration
        
        if duration < 300: # Less than 5 minutes
            result["issue"] = "Duration too short (< 5 mins)"
            result["status"] = "Corrupted Duration"
        elif duration > 7200: # More than 2 hours
            result["issue"] = "Duration too long (> 2 hrs)"
            result["status"] = "Corrupted Duration"
        else:
            # Try fetching the first segment to see if it's reachable
            if first_segment:
                seg_url = first_segment if first_segment.startswith("http") else url.rsplit("/", 1)[0] + "/" + first_segment
                try:
                    seg_resp = await client.head(seg_url, timeout=5.0)
                    if seg_resp.status_code != 200:
                        result["issue"] = f"Segment HTTP {seg_resp.status_code}"
                        result["status"] = "Failed (Segment unreachable)"
                    else:
                        result["status"] = "Healthy"
                except Exception as e:
                    result["issue"] = f"Segment fetch error: {str(e)}"
                    result["status"] = "Failed (Segment unreachable)"
            else:
                result["issue"] = "No segments found"
                result["status"] = "Failed (Empty playlist)"
                
    except Exception as e:
        result["issue"] = f"Request error: {str(e)}"
        result["status"] = "Failed (Network Error)"
        
    return result

async def main():
    db = databases.Database(db_url)
    await db.connect()
    
    query = 'SELECT "anilistId", "episodeNumber", "providerId", "episodeUrl" FROM episodes WHERE "episodeUrl" LIKE \'%tg-proxy%\''
    rows = await db.fetch_all(query)
    
    print(f"Starting diagnosis for {len(rows)} TG Proxy episodes...\n")
    
    healthy = 0
    corrupted_duration = []
    unreachable = []
    
    async with httpx.AsyncClient() as client:
        tasks = [check_episode(client, row) for row in rows]
        results = await asyncio.gather(*tasks)
        
        for r in results:
            if r["status"] == "Healthy":
                healthy += 1
            elif r["status"] == "Corrupted Duration":
                corrupted_duration.append(r)
            else:
                unreachable.append(r)
                
    print(f"--- DIAGNOSIS RESULTS ---")
    print(f"Total checked: {len(rows)}")
    print(f"Healthy: {healthy}")
    print(f"Corrupted Duration: {len(corrupted_duration)}")
    print(f"Unreachable / Infinite Loading: {len(unreachable)}\n")
    
    if corrupted_duration:
        print("--- CORRUPTED DURATION EPISODES ---")
        for r in corrupted_duration:
            print(f"- Anime {r['anime_id']} Ep {r['ep_num']} ({r['provider']}): {r['duration']:.2f} seconds ({r['issue']})")
            
    if unreachable:
        print("\n--- UNREACHABLE EPISODES (Infinite Loading) ---")
        for r in unreachable:
            print(f"- Anime {r['anime_id']} Ep {r['ep_num']} ({r['provider']}): {r['issue']}")

    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
