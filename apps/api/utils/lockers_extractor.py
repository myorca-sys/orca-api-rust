from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Konstanta
# ──────────────────────────────────────────────────────────────────────────

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_GOFILE_TOKEN_SALT = "5d4f7g8sd45fsd"
_GOFILE_TOKEN_BUCKET_SEC = 14400 

_DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)

class LockerExtractionError(Exception): pass
class TokenNotFoundError(LockerExtractionError): pass
class DirectUrlNotFoundError(LockerExtractionError): pass
class UpstreamHttpError(LockerExtractionError): pass
class PasswordRequiredError(LockerExtractionError): pass

@dataclass(slots=True, frozen=True)
class DirectLink:
    url: str
    filename: str | None = None
    size: int | None = None
    required_headers: dict[str, str] = field(default_factory=dict)
    host: str = ""

_RE_KRAKEN_TOKEN = re.compile(
    r'id=["\']dl-token["\']\s+[^>]*value=["\']([^"\']+)["\']', re.I
)
_RE_KRAKEN_HASH = re.compile(
    r'data-file-hash=["\']([a-f0-9]+)["\']', re.I
)

async def extract_krakenfiles(url: str, client: httpx.AsyncClient) -> str:
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = await client.get(url, headers=headers, follow_redirects=True)
    except httpx.HTTPError as e:
        raise UpstreamHttpError(f"Krakenfiles GET gagal: {e!r}") from e

    if resp.status_code != 200:
        raise UpstreamHttpError(f"Krakenfiles view page HTTP {resp.status_code} untuk {url}")

    html = resp.text
    soup = BeautifulSoup(html, "lxml")

    token_el = soup.find("input", id="dl-token")
    token: str | None = token_el.get("value") if token_el else None
    if not token:
        m = _RE_KRAKEN_TOKEN.search(html)
        token = m.group(1) if m else None
    if not token:
        raise TokenNotFoundError("Krakenfiles: input#dl-token tidak ditemukan")

    hashes = [
        el["data-file-hash"]
        for el in soup.find_all(attrs={"data-file-hash": True})
        if el.get("data-file-hash")
    ]
    if not hashes:
        m = _RE_KRAKEN_HASH.search(html)
        if m:
            hashes = [m.group(1)]
    if not hashes:
        raise TokenNotFoundError("Krakenfiles: data-file-hash tidak ditemukan")
    file_hash = hashes[0]

    post_url = f"https://krakenfiles.com/download/{file_hash}"
    multipart: dict[str, tuple[None, str]] = {"token": (None, token)}
    post_headers = {
        **headers,
        "Accept": "application/json, text/plain, */*",
        "Referer": url,
        "Origin": "https://krakenfiles.com",
        "hash": file_hash,
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        post_resp = await client.post(post_url, files=multipart, headers=post_headers)
    except httpx.HTTPError as e:
        raise UpstreamHttpError(f"Krakenfiles POST gagal: {e!r}") from e

    if post_resp.status_code != 200:
        raise UpstreamHttpError(f"Krakenfiles POST HTTP {post_resp.status_code}")

    try:
        payload = post_resp.json()
    except ValueError as e:
        raise DirectUrlNotFoundError("Krakenfiles POST bukan JSON") from e

    direct = payload.get("url")
    if not direct or not isinstance(direct, str):
        raise DirectUrlNotFoundError("Krakenfiles response tanpa url")

    if direct.startswith("//"):
        direct = "https:" + direct
        
    return direct

_RE_GOFILE_FOLDER_ID = re.compile(r"gofile\.io/d/([^/?#]+)", re.I)

def _gofile_generate_website_token(user_agent: str, account_token: str, lang: str = "en-US") -> str:
    bucket = int(time.time() / _GOFILE_TOKEN_BUCKET_SEC)
    payload = f"{user_agent}::{lang}::{account_token}::{bucket}::{_GOFILE_TOKEN_SALT}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

async def extract_gofile(url: str, client: httpx.AsyncClient, *, password: str | None = None, lang: str = "en-US") -> DirectLink:
    m = _RE_GOFILE_FOLDER_ID.search(url)
    if not m:
        raise TokenNotFoundError("Gofile URL tidak valid")
    content_id = m.group(1)

    ua = _DEFAULT_UA
    base_headers = {
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": lang + ",en;q=0.9",
        "Origin": "https://gofile.io",
        "Referer": "https://gofile.io/",
    }

    try:
        acc_resp = await client.post("https://api.gofile.io/accounts", headers=base_headers, json={})
    except httpx.HTTPError as e:
        raise UpstreamHttpError(f"Gofile accounts gagal: {e!r}") from e

    if acc_resp.status_code != 200:
        raise UpstreamHttpError("Gofile accounts HTTP error")

    acc_data = acc_resp.json()
    account_token = acc_data.get("data", {}).get("token") if isinstance(acc_data.get("data"), dict) else None
    
    if not account_token:
        raise UpstreamHttpError("Gofile accounts tanpa token")

    website_token = _gofile_generate_website_token(ua, account_token, lang)

    api_url = f"https://api.gofile.io/contents/{content_id}"
    params = {
        "wt": website_token,
        "contentFilter": "",
        "page": "1",
        "pageSize": "1000",
        "sortField": "name",
        "sortDirection": "1",
    }
    
    api_headers = {
        **base_headers,
        "Authorization": f"Bearer {account_token}",
        "X-Website-Token": website_token,
        "X-BL": lang,
    }
    client.cookies.set("accountToken", account_token, domain=".gofile.io")

    try:
        c_resp = await client.get(api_url, params=params, headers=api_headers)
    except httpx.HTTPError as e:
        raise UpstreamHttpError(f"Gofile contents gagal: {e!r}") from e

    if c_resp.status_code != 200:
        raise UpstreamHttpError(f"Gofile contents HTTP {c_resp.status_code}")

    body = c_resp.json()
    status = body.get("status", "")
    if status != "ok":
        raise UpstreamHttpError(f"Gofile status error: {status}")

    data = body.get("data") or {}
    children = data.get("children") or {}
    
    chosen = None
    for item in children.values():
        if not isinstance(item, dict): continue
        mime = str(item.get("mimetype") or "")
        if mime.startswith("video/"):
            chosen = item
            break

    if not chosen:
        for item in children.values():
            if isinstance(item, dict) and item.get("type") == "file":
                chosen = item
                break

    if not chosen or not chosen.get("link"):
        raise DirectUrlNotFoundError("Gofile file link tidak ditemukan")

    direct_url = chosen["link"]
    required = {
        "User-Agent": ua,
        "Referer": "https://gofile.io/",
        "Cookie": f"accountToken={account_token}",
    }

    return DirectLink(
        url=direct_url,
        filename=chosen.get("name"),
        size=chosen.get("size"),
        required_headers=required,
        host="gofile",
    )

def build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=_DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": _DEFAULT_UA},
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
