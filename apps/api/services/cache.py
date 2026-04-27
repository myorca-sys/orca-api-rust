import json
import time
import asyncio
from services.config import UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
from services.clients import client

async def upstash_get(key: str):
    try:
        res = await client.get(f"{UPSTASH_REDIS_REST_URL}/get/{key}", headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
        data = res.json()
        if data.get('result'):
            return json.loads(data['result'])
    except Exception as e:
        print(f"[Upstash] Get error: {e}")
    return None

async def upstash_keys(pattern: str):
    try:
        url = f"{UPSTASH_REDIS_REST_URL}/keys/{pattern}"
        res = await client.get(url, headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})
        data = res.json()
        return data.get('result', [])
    except Exception as e:
        print(f"[Upstash] Keys error: {e}")
        return []

async def upstash_set(key: str, value: dict, ex: int = 3600, nx: bool = False):
    try:
        payload = json.dumps(value)
        command = ["SET", key, payload, "EX", str(ex)]
        if nx:
            command.append("NX")
        res = await client.post(UPSTASH_REDIS_REST_URL, headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"}, json=command)
        data = res.json()
        if "error" in data:
            print(f"[Upstash] Set error response: {data['error']}")
            return False
        result = data.get('result')
        return result == 'OK'
    except Exception as e:
        print(f"[Upstash] Set error: {e}")
    return False

def upstash_del(key: str):
    return client.post(f"{UPSTASH_REDIS_REST_URL}/del/{key}", headers={"Authorization": f"Bearer {UPSTASH_REDIS_REST_TOKEN}"})

async def swr_cache_get(key: str, fetch_fn, ttl: int = 3600, swr: int = 86400):
    cached = await upstash_get(key)
    now = int(time.time())
    
    if cached and isinstance(cached, dict) and 'stale_at' in cached:
        stale_at = cached.get('stale_at', 0)
        expires_at = cached.get('expires_at', 0)
        
        if now < stale_at:
            return cached['data']
        
        if now < expires_at:
            asyncio.create_task(swr_cache_refresh(key, fetch_fn, ttl, swr))
            return cached['data']
    elif cached and not isinstance(cached, dict):
        return cached
    elif cached and 'data' not in cached:
        return cached

    data = await fetch_fn()
    if data:
        payload = {
            'data': data,
            'stale_at': now + ttl,
            'expires_at': now + swr,
            'created_at': now
        }
        await upstash_set(key, payload, ex=swr)
    return data

async def swr_cache_refresh(key: str, fetch_fn, ttl: int, swr: int):
    try:
        data = await fetch_fn()
        if data:
            now = int(time.time())
            payload = {
                'data': data,
                'stale_at': now + ttl,
                'expires_at': now + swr,
                'created_at': now
            }
            await upstash_set(key, payload, ex=swr)
    except Exception as e:
        print(f"[SWR] Background refresh error for {key}: {e}")

import hashlib

def _slug_hash(provider_id: str, slug: str) -> str:
    return hashlib.sha256(f"{provider_id}:{slug}".encode()).hexdigest()[:16]

async def get_reconciler_cache(provider_id: str, slug: str) -> dict | None:
    key = f"recon:{provider_id}:{_slug_hash(provider_id, slug)}"
    return await upstash_get(key)

async def set_reconciler_cache(provider_id: str, slug: str, result: dict) -> None:
    key = f"recon:{provider_id}:{_slug_hash(provider_id, slug)}"
    await upstash_set(key, result, ex=604800)
