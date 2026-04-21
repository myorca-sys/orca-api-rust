import asyncio
import httpx
import sys
import os

# Ensure apps.api is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from apps.api.services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

async def flush():
    print("Flushing Upstash Redis...")
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{UPSTASH_REDIS_REST_URL}/FLUSHDB", 
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
        )
        print("FLUSHDB result:", res.json())

if __name__ == "__main__":
    asyncio.run(flush())
