import asyncio
from dotenv import load_dotenv

load_dotenv("apps/api/.env")

async def test():
    from apps.api.services.queue import enqueue_ingest_batch
    print("Mencoba memanggil enqueue_ingest_batch...")
    await enqueue_ingest_batch()
    # Wait a second to allow background task to log
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test())
