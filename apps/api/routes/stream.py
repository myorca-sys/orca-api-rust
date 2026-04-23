import urllib.parse
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
import httpx
import re
import time
from utils.ssrf_guard import validate_scrape_url
from services.config import HEADERS
from db.connection import database
from services.providers import oploverz_provider, otakudesu_provider, samehadaku_provider, extractor

router = APIRouter()

# --- Configuration ---
VIDEO_PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "identity;q=1, *;q=0",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

CDN_DOMAINS = [
    "googlevideo.com",
    "blogger.com",
    "blogspot.com",
    "cloudfront.net",
    "akamaihd.net",
    "discordapp.com",
    "fbcdn.net"
]

def _is_video_cdn(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower()
    return any(cdn in domain for cdn in CDN_DOMAINS)

@router.options('/v1/stream')
async def stream_video_options():
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization",
            "Access-Control-Max-Age": "86400",
        }
    )

@router.get('/v1/stream')
async def stream_video(url: str, request: Request):
    # Parse custom Cookie injected by extractor (e.g. Gofile accountToken)
    custom_cookie = None
    if '|' in url:
        url, custom_cookie = url.split('|', 1)
        
    try:
        validate_scrape_url(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    range_header = request.headers.get("range")
    headers = VIDEO_PROXY_HEADERS.copy()
    if range_header:
        headers["Range"] = range_header
        
    if custom_cookie:
        headers["Cookie"] = custom_cookie
        # Gofile also requires matching User-Agent and Referer
        headers["Referer"] = "https://gofile.io/"

    # Special handling for HLS (.m3u8)
    if url.split('?')[0].endswith('.m3u8'):
        return await _proxy_hls(url, headers)

    # Route 1: Direct CDN Streaming (No HEAD request to avoid 403)
    if _is_video_cdn(url):
        return await _proxy_video_direct(url, headers)
    
    # Route 2: Standard Validation (HEAD first)
    return await _proxy_video_with_head(url, headers, range_header)

async def _proxy_hls(url: str, headers: dict):
    async with httpx.AsyncClient(verify=True, timeout=10.0) as client:
        resp = await client.get(url, headers=headers, follow_redirects=True)
        content = resp.text
        base_url = "/".join(url.split('/')[:-1])
        lines = []
        for line in content.splitlines():
            if line.startswith('#') or not line.strip():
                lines.append(line)
            else:
                original_link = line.strip()
                if not original_link.startswith('http'):
                    original_link = f"{base_url}/{original_link}"
                proxied_link = f"/api/v1/stream?url={urllib.parse.quote_plus(original_link)}"
                lines.append(proxied_link)
        return Response(
            content="\n".join(lines),
            media_type="application/vnd.apple.mpegurl",
            headers={"Access-Control-Allow-Origin": "*"}
        )

async def _proxy_video_direct(url: str, headers: dict):
    async def generate():
        async with httpx.AsyncClient(verify=True, timeout=60.0) as client:
            try:
                async with client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
                    # Forward status from the GET response itself
                    async for chunk in resp.aiter_bytes(chunk_size=256 * 1024):
                        yield chunk
            except Exception as e:
                print(f"[Stream Proxy] Direct error: {e}")

    # For direct CDN, we risk not having content-length in advance but it bypasses 403 HEAD
    return StreamingResponse(generate(), media_type="video/mp4", headers={
        "Access-Control-Allow-Origin": "*",
        "Accept-Ranges": "bytes",
    })

async def _proxy_video_with_head(url: str, headers: dict, range_header: str | None):
    async def generate():
        async with httpx.AsyncClient(verify=True, timeout=60.0) as client:
            try:
                async with client.stream("GET", url, headers=headers, follow_redirects=True) as resp:
                    async for chunk in resp.aiter_bytes(chunk_size=128 * 1024):
                        yield chunk
            except Exception as e:
                print(f"[Stream Proxy] Streaming error: {e}")

    async with httpx.AsyncClient(verify=True, timeout=10.0) as head_client:
        try:
            head_resp = await head_client.head(url, headers=headers, follow_redirects=True)
            if head_resp.status_code == 403:
                # Fallback to direct if HEAD fails
                return await _proxy_video_direct(url, headers)
                
            response_headers = {
                "Content-Type": head_resp.headers.get("Content-Type", "video/mp4"),
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600" if not range_header else "no-cache"
            }
            if "Content-Range" in head_resp.headers:
                response_headers["Content-Range"] = head_resp.headers["Content-Range"]
            if "Content-Length" in head_resp.headers:
                response_headers["Content-Length"] = head_resp.headers["Content-Length"]
                
            return StreamingResponse(generate(), status_code=head_resp.status_code, headers=response_headers)
        except Exception:
            return await _proxy_video_direct(url, headers)

@router.get('/v1/stream/debug')
async def debug_stream(url: str):
    is_cdn = _is_video_cdn(url)
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    expire = qs.get('expire', ['N/A'])[0]
    
    headers = VIDEO_PROXY_HEADERS.copy()
    async with httpx.AsyncClient(verify=True, timeout=5.0) as client:
        try:
            h = await client.head(url, headers=headers, follow_redirects=True)
            head_status = h.status_code
        except Exception as e:
            head_status = str(e)
            
        try:
            async with client.stream("GET", url, headers={**headers, "Range": "bytes=0-100"}, follow_redirects=True) as r:
                get_status = r.status_code
                content_type = r.headers.get("Content-Type")
        except Exception as e:
            get_status = str(e)
            content_type = None

    return {
        "url_info": {"is_cdn": is_cdn, "expire": expire, "domain": parsed.netloc},
        "test_results": {"head_status": head_status, "get_status": get_status, "content_type": content_type},
        "proxy_headers": headers
    }
