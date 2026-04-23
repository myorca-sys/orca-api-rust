import httpx
import re
import urllib.parse
import time
import random
import string
import asyncio
import logging
import yt_dlp
from utils.ssrf_guard import SSRFSafeTransport
from utils.tls_spoof import TLSSpoofTransport
from utils.lockers_extractor import extract_gofile, build_client, LockerExtractionError

# ── Konfigurasi yt-dlp yang ringan ──────────────────────────────────────────
YDL_OPTS: dict = {
    "skip_download": True,
    "extract_flat": False,
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best[ext=mp4]/best",
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
    "socket_timeout": 10,
    "retries": 3,
    "fragment_retries": 3,
    "writesubtitles": False,
    "writeautomaticsub": False,
    "writethumbnail": False,
    "writedescription": False,
    "writeinfojson": False,
    "writeannotations": False,
    "embed_subs": False,
    "embedthumbnail": False,
    "addmetadata": False,
    "cachedir": False,
}

def _extract_video_info_blocking(url: str) -> str:
    """Fungsi synchronous (blocking) untuk memanggil yt-dlp."""
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("yt-dlp mengembalikan info kosong")

    video_url = None
    formats = info.get("formats") or []

    if formats:
        mp4_formats = [
            f for f in formats
            if f.get("ext") == "mp4" and f.get("url") and f.get("vcodec") != "none"
        ]
        if mp4_formats:
            best = max(mp4_formats, key=lambda f: (f.get("height") or 0))
            video_url = best["url"]
        else:
            for f in reversed(formats):
                if f.get("url"):
                    video_url = f["url"]
                    break

    if not video_url:
        video_url = info.get("url") or info.get("manifest_url")

    if not video_url:
        raise ValueError("Tidak ada URL video yang bisa diekstraksi dari halaman ini")

    return video_url

class SmartExtractor:
    """Generic fallback: cari .m3u8 / .mp4 URL dari HTML apapun"""
    
    PATTERNS = [
        # HLS manifest
        r'(?:file|src|source|url)\s*[:=]\s*["\']?(https?://[^/]+/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
        # Direct MP4
        r'(?:file|src|source|url)\s*[:=]\s*["\']?(https?://[^/]+/[^\s"\'<>]+\.mp4[^\s"\'<>]*)',
        # Google Video
        r'(https?://[a-z0-9\-]+\.googlevideo\.com/videoplayback[^\s"\'<>]+)',
        # Source tag
        r'<source[^>]+src=["\']([^"\']+(?:\.m3u8|\.mp4)[^"\']*)["\']',
        # JWPlayer / VideoJS sources array
        r'sources\s*:\s*\[\s*\{[^}]*(?:file|src)\s*:\s*["\']([^"\']+)["\']',
    ]
    
    def extract_from_html(self, html: str) -> str | None:
        for pattern in self.PATTERNS:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                url = match.group(1).replace('&amp;', '&')
                if any(ext in url for ext in ['.m3u8', '.mp4', '.webm', 'videoplayback']):
                    return url
        return None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
}

class UniversalExtractor:
    def __init__(self, concurrency_limit=20):
        self.client = httpx.AsyncClient(
            transport=SSRFSafeTransport(),
            verify=False, # Ignore SSL errors for shady providers
            headers=HEADERS,
            timeout=15.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20)
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self._tls = TLSSpoofTransport

    async def extract_raw_video(self, embed_url: str) -> str:
        async with self.semaphore:
            return await self._extract_raw_video_impl(embed_url)

    async def _extract_raw_video_impl(self, embed_url: str) -> str:
        url = embed_url
        
        # Wibufile direct handling (already raw mp4, skip fetching to save time)
        if 'wibufile' in url.lower() and url.endswith(('.mp4', '.m3u8')):
            return url
            
        if 'api.wibufile.com/embed/' in url.lower():
            # Wibufile requires a referer to avoid 'Access denied' iframe check
            try:
                # Guess referer based on likely origin, or just use a generic samehadaku referer
                # since we only scrape samehadaku and oploverz
                ref = "https://v2.samehadaku.how/"
                res = await self.client.get(url, headers={"Referer": ref})
                
                # Check for sources: [{"file":"...mp4"}]
                match = re.search(r'sources:\s*\[\{"file":"([^"]+)"', res.text)
                if match:
                    return match.group(1).replace('\\/', '/')
            except Exception as e:
                print(f"[Extractor] Wibufile embed extract error: {e}")
            
        # Handle if the input is actually an iframe HTML string (like what wajik-anime-api generateSrcFromIframeTag does)
        if '<iframe' in url.lower():
            iframe_match = re.search(r'<iframe[^>]+src="([^"]+)"', url, re.IGNORECASE)
            if iframe_match:
                url = iframe_match.group(1)
                
        try:
            if 'kuramadrive' in url or 'kuramanime' in url or 'kuroplayer' in url or 'kuronime' in url:
                # wajik-anime-api extracts kuramanime from #player source
                # Try fetching the embed url and getting the source
                res = await self.client.get(url)
                match = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                if match:
                    return match.group(1).replace('&amp;', '&')
                
                # Kuroplayer specific fallback
                match2 = re.search(r'file\s*:\s*["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                if match2:
                    return match2.group(1).replace('&amp;', '&')
            elif 'desustream' in url or 'desudrives' in url:
                fetch_url = f"{url}&mode=json" if '?' in url else f"{url}?mode=json"
                res = await self.client.get(fetch_url)
                try:
                    data = res.json()
                    if data.get('ok') and data.get('video'):
                        return await self._extract_raw_video_impl(data['video'].replace('&amp;', '&'))
                except Exception:
                    # It might return HTML instead of JSON
                    match = re.search(r'<source[^>]+src=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                    if match:
                        return match.group(1).replace('&amp;', '&')
                    
                    iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', res.text, re.IGNORECASE)
                    if iframe_match:
                        iframe_src = iframe_match.group(1).replace('&amp;', '&')
                        if iframe_src.startswith('//'):
                            iframe_src = 'https:' + iframe_src
                        return await self._extract_raw_video_impl(iframe_src)
            elif 'blogger.com' in url or 'blogspot.com' in url:
                try:
                    # Coba curl_cffi dulu untuk bypass CF
                    html = await self._tls.get(url)
                except Exception:
                    res = await self.client.get(url)
                    html = res.text
                
                # Coba semua format
                patterns = [
                    r'"play_url"\s*:\s*"([^"]+)"',
                    r'file\s*:\s*["\']([^"\']+\.(?:mp4|m3u8)[^"\']*)["\']',
                    r'"sources"\s*:\s*\[\s*\{\s*"file"\s*:\s*"([^"]+)"',
                    r'var\s+urlPlay\s*=\s*["\']([^"\']+)["\']',
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        url_found = match.group(1)
                        url_found = url_found.encode('utf-8').decode('unicode_escape')
                        if url_found.startswith('http'):
                            return url_found
                
                # Fallback SmartExtractor
                smart = SmartExtractor()
                result = smart.extract_from_html(html)
                if result:
                    return result
            elif 'krakenfiles.com' in url:
                res = await self.client.get(url)
                token_match = re.search(r'var\s+token\s*=\s*["\']([^"\']+)["\']', res.text)
                form_match = re.search(r'url:\s*["\'](//krakenfiles.com/download/[^"\']+)["\']', res.text)
                if token_match and form_match:
                    dl_url = "https:" + form_match.group(1)
                    res2 = await self.client.post(dl_url, data={"token": token_match.group(1)})
                    try:
                        data = res2.json()
                        if data.get('status') == 'ok' and data.get('url'):
                            return data['url']
                    except Exception:
                        pass
            elif 'gofile.io' in url:
                try:
                    res = await extract_gofile(url, self.client)
                    return f"{res.url}|{res.required_headers.get('Cookie','')}"
                except LockerExtractionError as e:
                    print(f"[Extractor] Gofile error: {e}")
                    pass
            elif 'pixeldrain.com' in url:
                if "/u/" in url:
                    file_id = url.split('/u/')[-1].split('?')[0]
                    return f"https://pixeldrain.com/api/file/{file_id}"
                return url
            elif '4meplayer' in url or 'oplo2.' in url:
                # Coba dapat hash dari fragment
                hash_id = url.split('#')[-1] if '#' in url else None
                
                # Kalau tidak ada fragment, parse dari path
                if not hash_id or hash_id == url:
                    from urllib.parse import urlparse
                    path = urllib.parse.urlparse(url).path
                    hash_id = path.strip('/').split('/')[-1]
                
                if not hash_id:
                    return url
                    
                api_url = f"https://oplo2.4meplayer.pro/api/source/{hash_id}"
                try:
                    res = await self.client.post(api_url, data={'r': '', 'd': 'oplo2.4meplayer.pro'})
                    data = res.json()
                    if data.get('success') and data.get('data'):
                        sources = data['data']
                        for s in sources:
                            if '720' in str(s.get('label', '')):
                                return s.get('file', url)
                        return sources[0].get('file', url) if sources else url
                except Exception:
                    pass
                
                # Fallback: scrape the iframe HTML directly for video sources if API fails
                try:
                    res_html = await self.client.get(url)
                    match = re.search(r'sources:\s*\[\s*{\s*(?:file|src):\s*[\'"]([^\'"]+)[\'"]', res_html.text)
                    if match:
                        return match.group(1)
                    match2 = re.search(r'(?:file|src):\s*[\'"](https?://[^\'"]+\.(?:m3u8|mp4)[^\'"]*)[\'"]', res_html.text)
                    if match2:
                        return match2.group(1)
                except Exception as e:
                    print(f"[Extractor] 4meplayer fallback error: {e}")
                return url
            elif 'streamtape' in url:
                try:
                    res = await self.client.get(url)
                    html = res.text
                except Exception:
                    html = ""
                
                token_match = re.search(r"(//streamtape\.com/get_video\?id=[^&'\"]+&expires=[^&'\"]+&ip=[^&'\"]+&token=[^&'\"]+)", html)
                if token_match:
                    return 'https:' + token_match.group(1)
                
                # Fallback ke curl_cffi
                try:
                    html = await self._tls.get(url)
                    token_match = re.search(r"(//streamtape\.com/get_video\?id=[^&'\"]+&expires=[^&'\"]+&ip=[^&'\"]+&token=[^&'\"]+)", html)
                    if token_match:
                        return 'https:' + token_match.group(1)
                    
                    smart_ex = SmartExtractor()
                    res_smart = smart_ex.extract_from_html(html)
                    if res_smart: return res_smart
                except Exception as e:
                    print(f"[Extractor] TLS fallback error for streamtape: {e}")

            elif 'mp4upload' in url:
                try:
                    res = await self.client.get(url)
                    html = res.text
                except Exception:
                    html = ""
                
                match = re.search(r'"file":"(https?://[^"]+\.mp4[^"]*)"', html)
                if match: return match.group(1).replace('\\/', '/')
                
                # Fallback ke curl_cffi
                try:
                    html = await self._tls.get(url)
                    match = re.search(r'"file":"(https?://[^"]+\.mp4[^"]*)"', html)
                    if match: return match.group(1).replace('\\/', '/')
                    
                    smart_ex = SmartExtractor()
                    res_smart = smart_ex.extract_from_html(html)
                    if res_smart: return res_smart
                except Exception as e:
                    print(f"[Extractor] TLS fallback error for mp4upload: {e}")
            elif 'dood' in url or 'doodstream' in url or 'filelions' in url or 'streamwish' in url or 'vidhide' in url:
                try:
                    # Leverage yt-dlp for heavily obfuscated hosts
                    print(f"[Extractor] Using yt-dlp for {url}")
                    result = await asyncio.wait_for(
                        asyncio.to_thread(_extract_video_info_blocking, url),
                        timeout=30.0
                    )
                    if result:
                        return result
                except Exception as e:
                    print(f"[Extractor] yt-dlp extraction failed for {url}: {e}")
        except Exception as e:
            print(f"[Extractor] Error resolving {url}: {e}")
        
        # SmartExtractor Fallback
        try:
            print(f"[Extractor] Falling back to SmartExtractor for {url}")
            res = await self.client.get(url)
            
            if res.status_code in [403, 404, 429, 500, 502, 503]:
                domain = urllib.parse.urlparse(url).netloc
                print(f"[Extractor] Domain {domain} failed with {res.status_code}. Blacklisting for 5 minutes.")
                self.failed_domains[domain] = time.time() + 300  # Blacklist for 5 minutes
                return url
                
            html = res.text
            smart_ex = SmartExtractor()
            result = smart_ex.extract_from_html(html)
            if result:
                print(f"[Extractor] SmartExtractor found stream: {result}")
                return result
        except httpx.HTTPStatusError as e:
            domain = urllib.parse.urlparse(url).netloc
            print(f"[Extractor] Domain {domain} threw HTTP error {e.response.status_code}. Blacklisting for 5 minutes.")
            self.failed_domains[domain] = time.time() + 300
        except httpx.ConnectTimeout:
            domain = urllib.parse.urlparse(url).netloc
            print(f"[Extractor] Domain {domain} timed out. Blacklisting for 5 minutes.")
            self.failed_domains[domain] = time.time() + 300
        except Exception as e:
            print(f"[Extractor] SmartExtractor fallback error on {url}: {e}")
            
        return url
