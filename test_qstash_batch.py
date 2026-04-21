import asyncio
import os
import httpx
from dotenv import load_dotenv

load_dotenv("apps/api/.env")
QSTASH_TOKEN = os.getenv("QSTASH_TOKEN")

async def test_publish():
    qstash_url = os.getenv("QSTASH_URL", "https://qstash.upstash.io").rstrip("/")
    target_url = "https://jonyyyyyyyu-anime-scraper-api.hf.space/api/v2/webhook/ingest-batch"
    
    headers = {
        "Authorization": f"Bearer {QSTASH_TOKEN}",
        "Content-Type": "application/json",
    }
        
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{qstash_url}/v2/publish/" + target_url,
            headers=headers,
            json={"action": "run_batch"}
        )
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")

if __name__ == "__main__":
    asyncio.run(test_publish())
