import asyncio
from dotenv import load_dotenv

load_dotenv("apps/api/.env")

async def test():
    from apps.api.services.cache import upstash_del
    await upstash_del("lock:ingest_batch_trigger")
    from apps.api.services.queue import enqueue_ingest_batch
    print("Mencoba memanggil enqueue_ingest_batch...")
    await enqueue_ingest_batch()
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test())
