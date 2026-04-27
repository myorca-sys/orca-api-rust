import asyncio
import sys
import os
import httpx
from dotenv import load_dotenv

# Menambahkan path agar bisa import dari modul apps/api
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from services.cache import client, upstash_keys
from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
from db.connection import database

# Load environment variables dari root project
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))
# Load .env fallback
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

CLOUDFLARE_ZONE_ID = os.getenv("CLOUDFLARE_ZONE_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

async def clear_all():
    print("🚀 Memulai proses Purge Cache (Cache Buster CLI)...")
    
    try:
        # 1. Postgres Cache
        print("\n[1/3] Membersihkan Postgres video_cache...")
        await database.connect()
        await database.execute("DELETE FROM video_cache")
        await database.disconnect()
        print("✅ Postgres video_cache bersih.")
    except Exception as e:
        print(f"❌ Gagal membersihkan Postgres: {e}")
    
    try:
        # 2. Upstash Redis
        print("\n[2/3] Membersihkan Upstash Redis Stream & Lock Keys...")
        keys = await upstash_keys("stream:*")
        locks = await upstash_keys("lock:*")
        all_keys = keys + locks
        
        if all_keys:
            for k in all_keys:
                await client.post(
                    f"{UPSTASH_REDIS_REST_URL}/del/{k}", 
                    headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}
                )
            print(f"✅ Berhasil menghapus {len(all_keys)} keys dari Redis.")
        else:
            print("✅ Tidak ada keys yang perlu dihapus di Redis.")
    except Exception as e:
        print(f"❌ Gagal membersihkan Redis: {e}")
    
    # 3. Cloudflare Edge Cache
    print("\n[3/3] Membersihkan Cloudflare Edge Cache...")
    if not CLOUDFLARE_ZONE_ID or not CLOUDFLARE_API_TOKEN:
        print("⚠️  CLOUDFLARE_ZONE_ID atau CLOUDFLARE_API_TOKEN tidak ditemukan di .env!")
        print("💡 Silakan tambahkan kredensial tersebut di root .env agar cache CDN/Edge bisa di-purge secara otomatis.")
    else:
        try:
            url = f"https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/purge_cache"
            headers = {
                "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {"purge_everything": True}
            
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    print("✅ Cloudflare Edge Cache berhasil di-purge!")
                else:
                    print(f"❌ Gagal mem-purge Cloudflare. Status: {response.status_code}, Res: {response.text}")
        except Exception as e:
            print(f"❌ Terjadi kesalahan saat mem-purge Cloudflare: {e}")
                
    print("\n🎉 Cache Buster CLI selesai!")

if __name__ == "__main__":
    asyncio.run(clear_all())
