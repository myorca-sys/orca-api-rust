import asyncio
from apps.api.utils.extractor import UniversalExtractor

async def test():
    extractor = UniversalExtractor()
    url = "https://www.blogger.com/video.g?token=AD6v5dzT6AvvjLfiTafHVB1pfIH8PBY5GnNNZskhvuRrCFbWAyBeF4rjwQYfKS_t0CZrs9K_oFWhFXL9jg7sNS9NBW02YT3RCKzv7iRdjflXi_NybAzvuVP71utrcdrZ2D9V5RioJC4q"
    print(f"Extracting: {url}")
    try:
        raw = await extractor.extract_raw_video(url)
        print("Result:", raw)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
