import asyncio
import time
import httpx

async def test_download():
    url = "https://pixeldrain.com/api/file/rYUUkSdm"
    print(f"Mencoba mengunduh dari Pixeldrain: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://pixeldrain.com/"
    }
    
    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True, verify=False) as client:
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code not in (200, 206):
                    print(f"Gagal! HTTP Status: {response.status_code}")
                    return
                
                total_size = int(response.headers.get("Content-Length", 0))
                print(f"Total Ukuran File: {total_size / 1024 / 1024:.2f} MB")
                
                downloaded = 0
                last_print = 0
                
                # Download max 50MB to test speed
                max_test_size = 50 * 1024 * 1024 
                
                async for chunk in response.aiter_bytes(chunk_size=1024*1024):
                    downloaded += len(chunk)
                    
                    # Print progress every ~5MB
                    if downloaded - last_print > 5 * 1024 * 1024:
                        elapsed = time.time() - start_time
                        speed = (downloaded / 1024 / 1024) / elapsed
                        print(f"Terunduh: {downloaded / 1024 / 1024:.2f} MB | Kecepatan: {speed:.2f} MB/s")
                        last_print = downloaded
                        
                    if downloaded >= max_test_size:
                        print("Menghentikan tes (sudah mencapai 50MB).")
                        break
                        
                total_time = time.time() - start_time
                final_speed = (downloaded / 1024 / 1024) / total_time
                print(f"Rata-rata Kecepatan Download: {final_speed:.2f} MB/s")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_download())
