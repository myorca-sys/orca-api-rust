import asyncio
import sys
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps/api"))

from services.providers import kuronime_provider

async def main():
    print("Testing KuronimeProvider...")
    
    try:
        # Panggil method search jika ada
        if hasattr(kuronime_provider, 'search'):
             print("\n--- Kuronime Search Results for 'one piece' ---")
             results = await kuronime_provider.search("one piece")
             for item in results[:10]:
                 print(f"  - {item.get('title')} (URL: {item.get('url')})")
        else:
             print("No search method found on kuronime_provider")
             
        # Kuronime tidak punya get_home di BaseProvider, kita cek ketersediaan search
        print("\n--- Kuronime Search Results for 'dan da dan' ---")
        results = await kuronime_provider.search("dan da dan")
        for item in results[:5]:
             print(f"  - {item.get('title')} (URL: {item.get('url')})")
            
    except Exception as e:
        print(f"Error calling Kuronime API: {e}")

if __name__ == "__main__":
    asyncio.run(main())