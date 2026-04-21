import asyncio
import os
import sys

# setup path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps/api'))

from services.providers import kuronime_provider, oploverz_provider

async def search():
    query = "tensei shitara slime"
    print(f"--- Kuronime Search: {query} ---")
    k_res = await kuronime_provider.search(query)
    for r in k_res:
        print(r['title'], "->", r['url'])

    print(f"\n--- Oploverz Search: {query} ---")
    o_res = await oploverz_provider.search(query)
    for r in o_res:
        print(r['title'], "->", r['url'])

if __name__ == "__main__":
    asyncio.run(search())
