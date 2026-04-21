import asyncio
import sys
import os

# Add apps/api to path
sys.path.append(os.path.abspath("apps/api"))

from services.scraper.providers.kuronime.provider import KuronimeProvider
from services.transport import ProviderTransport

async def check():
    print("Testing KuronimeProvider...")
    transport = ProviderTransport()
    provider = KuronimeProvider(transport=transport)
    
    try:
        # Panggil get_home() untuk melihat daftar terbaru
        home_data = await provider.get_home()
        print("\n--- Kategori Homepage Kuronime ---")
        for category in home_data:
            print(f"\nKategori: {category.get('title')}")
            for item in category.get('items', [])[:5]: # Tampilkan 5 teratas
                print(f"  - {item.get('title')} (Ep: {item.get('episode')})")
    except Exception as e:
        print(f"Error calling get_home(): {e}")

if __name__ == "__main__":
    asyncio.run(check())
