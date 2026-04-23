import asyncio
import sys
import httpx
from bs4 import BeautifulSoup
import re
import base64

async def resolve_desustream(url: str):
    print(f"Membuka URL shortener: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://otakudesu.blog/"
    }
    
    async with httpx.AsyncClient(verify=False, follow_redirects=True, timeout=30.0) as client:
        res = await client.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'lxml')
        
        # Biasanya desustream memiliki script yang redirect atau tombol untuk diklik
        # Mari kita cari link tujuan
        link = None
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if 'http' in href and 'desustream' not in href:
                link = href
                break
                
        # Jika tidak ada, coba lihat apakah ada token base64 di script
        if not link:
            match = re.search(r'const\s+url\s*=\s*atob\("([^"]+)"\)', res.text)
            if match:
                link = base64.b64decode(match.group(1)).decode('utf-8')
                
        # Coba lihat struktur aslinya
        if not link:
            print("Gagal menemukan direct link, ini preview HTML-nya:")
            print(res.text[:500])
        else:
            print(f"\n✅ Berhasil mendapatkan URL Target: {link}")
            
        return link

if __name__ == "__main__":
    url = "https://link.desustream.com/?id=Uk83OUtycXp4T0NoTWt3RTFpTzBNdW9xSnA5Z3NXWnBJV1h1L1dTUkxOK3M3THhjcVo1SUN5ZkFFRHhrdzh0d2FXV09oMmpvc09WY2cyb2p6VEZpOUllbS9tVzNWVHhGZERHMnNPZ0hRRzdsMTZWZHEwbHRZdXRjR0VnQUR5SFBMZ0o2L0h1NlUzeGpGMUt5Skx0QTlraz0="
    asyncio.run(resolve_desustream(url))
