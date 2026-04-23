import httpx
import re
import sys
import asyncio
import os

async def download_gdrive(url: str, output_path: str):
    print(f"🔗 Memulai resolusi Google Drive: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30.0) as client:
        # 1. Buka URL awal untuk mendapatkan halaman peringatan virus
        res = await client.get(url, headers=headers)
        
        # 2. Cari token 'confirm' untuk file besar
        confirm_token = None
        match = re.search(r'confirm=([A-Za-z0-9_-]+)', res.text)
        if match:
            confirm_token = match.group(1)
        else:
            # Kadang token ada di dalam form action
            match2 = re.search(r'action="(/u/\d+/uc\?export=download&amp;id=[^"]+&amp;confirm=[^"]+)"', res.text)
            if match2:
                final_url = "https://drive.usercontent.google.com" + match2.group(1).replace('&amp;', '&')
                confirm_token = "found_in_action"
            else:
                match3 = re.search(r'href="(/download\?id=[^"]+&amp;export=download&amp;confirm=[^"]+)"', res.text)
                if match3:
                    final_url = "https://drive.usercontent.google.com" + match3.group(1).replace('&amp;', '&')
                    confirm_token = "found_in_href"

        if not confirm_token:
            print("❌ Gagal menemukan token konfirmasi Google Drive. File mungkin dihapus atau butuh login.")
            return

        if confirm_token not in ["found_in_action", "found_in_href"]:
            # Rangkai URL final
            file_id = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get('id', [None])[0]
            if not file_id:
                file_id = re.search(r'id=([a-zA-Z0-9_-]+)', res.url.query.decode('utf-8')).group(1)
            final_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={confirm_token}"

        print(f"🔓 Token Bypass ditemukan! Memulai unduhan ke '{output_path}'...")
        
        # 3. Stream download
        try:
            async with client.stream("GET", final_url, headers=headers) as response:
                if response.status_code != 200:
                    print(f"❌ Error: Server merespons dengan HTTP {response.status_code}")
                    return
                
                total_size = int(response.headers.get("Content-Length", 0))
                size_mb = total_size / (1024 * 1024)
                print(f"📦 Ukuran File: {size_mb:.2f} MB")
                
                with open(output_path, "wb") as f:
                    downloaded = 0
                    async for chunk in response.aiter_bytes(chunk_size=1024*1024): # 1MB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        dl_mb = downloaded / (1024 * 1024)
                        # Print progress di baris yang sama
                        sys.stdout.write(f"\r⏳ Progress: {dl_mb:.2f} MB / {size_mb:.2f} MB ({downloaded/total_size*100:.1f}%)")
                        sys.stdout.flush()
                        
                        # Stop setelah 20MB untuk demonstrasi agar tidak menghabiskan memori / kuota user,
                        # dihapus agar bisa download full file
                        # if downloaded > 20 * 1024 * 1024:
                        #     print("\n\n✅ [DEMO] Unduhan dihentikan pada 20MB untuk menghemat memori perangkat Android Anda.")
                        #     print("Script downloader ini berfungsi 100% sempurna untuk menarik file 2GB penuh dari Google Drive!")
                        #     return
                            
        except Exception as e:
            print(f"\n❌ Terjadi kesalahan saat mengunduh: {e}")

if __name__ == "__main__":
    url = "https://link.desustream.com/?id=Uk83OUtycXp4T0NoTWt3RTFpTzBNdW9xSnA5Z3NXWnBJV1h1L1dTUkxOK3M3THhjcVo1SUN5ZkFFRHhrdzh0d2FXV09oMmpvc09WY2cyb2p6VEZpOUllbS9tVzNWVHhGZERHMnNPZ0hRRzdsMTZWZHEwbHRZdXRjR0VnQUR5SFBMZ0o2L0h1NlUzeGpGMUt5Skx0QTlraz0="
    asyncio.run(download_gdrive(url, "Death_Note_720p.mp4"))
