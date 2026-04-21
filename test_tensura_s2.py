import asyncio
from apps.api.services.providers import samehadaku_provider

async def test_resolve():
    url = "https://v2.samehadaku.how/tensei-shitara-slime-datta-ken-season-2-episode-1/"
    print(f"Resolving: {url}")
    try:
        sources = await samehadaku_provider.get_episode_sources(url)
        print("Result:", sources)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_resolve())
