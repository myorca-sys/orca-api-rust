"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║          ADAPTIVE STREAM CACHE ENGINE  —  orca                               ║
║          Target: Near 0ms latency untuk episode stream sources                 ║
╠══════════════════════════════════════════════════════════════════════════════════╣
║  ARSITEKTUR MULTI-LAYER:                                                        ║
║                                                                                 ║
║  L0 ── In-Process LRU (0ms)       ← Hot cache per instance, no network I/O    ║
║  L1 ── Upstash Redis (1–5ms)      ← Distributed global cache                  ║
║  L2 ── Neon Postgres (10–30ms)    ← Persistent cold store + expiry tracking   ║
║  L3 ── Live Scrape (2000–8000ms)  ← Last resort, writes back to L0→L2         ║
║                                                                                 ║
║  FITUR KUNCI:                                                                   ║
║  • Stale-While-Revalidate (SWR)   → user tidak pernah nunggu refresh           ║
║  • Probabilistic Early Expiry     → mencegah "thundering herd" saat TTL habis  ║
║  • Adaptive TTL                   → TTL berdasarkan URL expiry parameter        ║
║  • Smart Prefetch Heat            → Background pre-resolve ep berikutnya       ║
║  • Circuit Breaker per Provider   → Provider down? skip instantly              ║
║  • Deduplication via Redis NX     → Tidak ada dua scrape job untuk key sama    ║
╚══════════════════════════════════════════════════════════════════════════════════╝

Drop-in replacement untuk services/pipeline.py functions.
Import dan gunakan StreamCacheEngine sebagai singleton.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import random
import time
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from db.connection import database
from services.cache import upstash_get, upstash_set, upstash_del
from services.providers import (
    oploverz_provider,
    otakudesu_provider,
    samehadaku_provider,
    doronime_provider,
    kuronime_provider,
    extractor,
)

logger = logging.getLogger("StreamCacheEngine")


# ══════════════════════════════════════════════════════════════════════════════
# § 1. CONSTANTS & CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class Config:
    # L0 LRU — in-process (per instance)
    L0_MAX_ENTRIES    = 512        # max episode cache entries in RAM
    L0_TTL_SECONDS    = 900        # 15 menit — hot entries; evicted after this

    # L1 Redis TTLs
    L1_FRESH_TTL      = 4 * 3600   # 4 jam — considered fresh
    L1_STALE_TTL      = 24 * 3600  # 24 jam — stale-while-revalidate window
    L1_LOCK_TTL       = 30         # 30 detik — scrape dedup lock

    # L2 Postgres
    L2_FALLBACK_TTL   = 4 * 3600   # jika tidak ada URL expiry

    # Probabilistic early expiry (Beta eviction)
    # Sumber: Vattani et al., "Cache stampede" paper
    BETA              = 1.0        # higher = more aggressive early refresh

    # Prefetch
    PREFETCH_LOOKAHEAD = 2         # pre-resolve N episodes ke depan
    PREFETCH_DELAY     = 0.3       # detik delay antar prefetch (rate limiting)

    # Circuit breaker
    CB_FAILURE_THRESHOLD = 3       # trip after N failures
    CB_RESET_TIMEOUT     = 60      # detik sebelum half-open retry

    # Provider scrape priority (lower = preferred)
    PROVIDER_PRIORITY = {
        "kuronime":   1,
        "samehadaku": 2,
        "oploverz":   3,
        "doronime":   4,
        "otakudesu":  5,
    }

    PROVIDERS = {
        "oploverz":   oploverz_provider,
        "otakudesu":  otakudesu_provider,
        "samehadaku": samehadaku_provider,
        "doronime":   doronime_provider,
        "kuronime":   kuronime_provider,
    }

    QUALITY_RANK = {"1080p": 5, "720p": 4, "480p": 3, "360p": 2, "Auto": 1}


# ══════════════════════════════════════════════════════════════════════════════
# § 2. DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CachedPayload:
    """Payload yang disimpan di semua layer cache."""
    sources:    list[dict]
    downloads:  list[dict]
    created_at: float
    expires_at: float  # waktu expired sebenarnya (dari URL param atau default)
    stale_at:   float  # setelah ini, SWR background refresh dipicu

    def is_fresh(self) -> bool:
        return time.time() < self.stale_at

    def is_usable(self) -> bool:
        """Masih bisa dipakai (stale tapi belum expired)."""
        return time.time() < self.expires_at

    def should_early_refresh(self, beta: float = Config.BETA) -> bool:
        """
        Probabilistic Early Expiry — XFetch algorithm.
        Sumber: https://en.wikipedia.org/wiki/Cache_stampede#Probabilistic_early_expiration
        Mencegah semua request serentak merevalidasi cache saat mendekati expiry.
        """
        delta   = self.expires_at - self.stale_at  # lebar stale window
        elapsed = time.time() - self.created_at
        if delta <= 0 or elapsed <= 0:
            return False
        # P(refresh) meningkat secara eksponensial saat mendekati expires_at
        return time.time() - beta * delta * math.log(random.random()) >= self.expires_at

    def to_redis(self) -> dict:
        return {
            "sources":    self.sources,
            "downloads":  self.downloads,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "stale_at":   self.stale_at,
        }

    @staticmethod
    def from_redis(data: dict) -> "CachedPayload":
        return CachedPayload(
            sources    = data.get("sources", []),
            downloads  = data.get("downloads", []),
            created_at = data.get("created_at", time.time()),
            expires_at = data.get("expires_at", time.time() + Config.L2_FALLBACK_TTL),
            stale_at   = data.get("stale_at",   time.time() + Config.L1_FRESH_TTL),
        )

    def to_response(self) -> dict:
        return {"sources": self.sources, "downloads": self.downloads}


# ══════════════════════════════════════════════════════════════════════════════
# § 3. L0 — IN-PROCESS LRU CACHE
# ══════════════════════════════════════════════════════════════════════════════

class LRUCache:
    """
    Thread-safe LRU dengan TTL per-entry.
    Menggunakan OrderedDict sehingga O(1) get/put/evict.
    """

    def __init__(self, max_size: int, default_ttl: int):
        self._store:    OrderedDict[str, tuple[CachedPayload, float]] = OrderedDict()
        self._max_size  = max_size
        self._ttl       = default_ttl
        self._lock      = asyncio.Lock()

    async def get(self, key: str) -> Optional[CachedPayload]:
        async with self._lock:
            if key not in self._store:
                return None
            payload, evict_at = self._store[key]
            if time.time() > evict_at:
                del self._store[key]
                return None
            # Move to end = most recently used
            self._store.move_to_end(key)
            return payload

    async def set(self, key: str, payload: CachedPayload) -> None:
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (payload, time.time() + self._ttl)
            # Evict LRU entry jika melebihi kapasitas
            if len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    @property
    def size(self) -> int:
        return len(self._store)


# ══════════════════════════════════════════════════════════════════════════════
# § 4. CIRCUIT BREAKER
# ══════════════════════════════════════════════════════════════════════════════

class CBState(Enum):
    CLOSED    = "closed"     # normal operation
    OPEN      = "open"       # failing, skip calls
    HALF_OPEN = "half_open"  # testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker per-provider.
    CLOSED → gagal N kali → OPEN (skip) → timeout → HALF_OPEN → sukses → CLOSED
    """
    provider_id: str
    threshold:   int   = Config.CB_FAILURE_THRESHOLD
    reset_time:  float = Config.CB_RESET_TIMEOUT
    _state:      CBState = field(default=CBState.CLOSED, init=False)
    _failures:   int     = field(default=0, init=False)
    _opened_at:  float   = field(default=0.0, init=False)

    @property
    def state(self) -> CBState:
        if self._state == CBState.OPEN:
            if time.time() - self._opened_at >= self.reset_time:
                self._state = CBState.HALF_OPEN
                logger.info(f"[CB:{self.provider_id}] HALF_OPEN — testing recovery")
        return self._state

    def is_allowed(self) -> bool:
        return self.state != CBState.OPEN

    def record_success(self) -> None:
        if self._state in (CBState.HALF_OPEN, CBState.CLOSED):
            self._failures = 0
            self._state    = CBState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold:
            if self._state != CBState.OPEN:
                self._state    = CBState.OPEN
                self._opened_at = time.time()
                logger.warning(
                    f"[CB:{self.provider_id}] OPEN — tripped after {self._failures} failures"
                )


# ══════════════════════════════════════════════════════════════════════════════
# § 5. CACHE KEY FACTORY
# ══════════════════════════════════════════════════════════════════════════════

class CacheKey:
    """Konsisten, deterministic key generation untuk semua layer."""

    @staticmethod
    def stream(episode_url: str) -> str:
        h = hashlib.blake2b(episode_url.encode(), digest_size=12).hexdigest()
        return f"stream:v3:{h}"

    @staticmethod
    def lock(episode_url: str) -> str:
        h = hashlib.blake2b(episode_url.encode(), digest_size=8).hexdigest()
        return f"lock:scrape:{h}"

    @staticmethod
    def prefetch_scheduled(anilist_id: int, ep_num: float) -> str:
        return f"prefetch:sched:{anilist_id}:{ep_num}"


# ══════════════════════════════════════════════════════════════════════════════
# § 6. URL UTILITY
# ══════════════════════════════════════════════════════════════════════════════

def extract_url_expiry(url: str) -> float:
    """
    Baca expiry dari URL parameter jika ada.
    Mendukung: ?expires=, ?expire=, ?exp=, ?e= (berbagai CDN format)
    """
    if not url:
        return time.time() + Config.L2_FALLBACK_TTL
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        for key in ("expires", "expire", "exp", "e"):
            if key in params:
                val = int(params[key][0])
                # Sanity check: harus di masa depan dan dalam 48 jam
                now = time.time()
                if now < val < now + 172800:
                    return float(val)
    except Exception:
        pass
    return time.time() + Config.L2_FALLBACK_TTL


def build_cached_payload(sources: list[dict], downloads: list[dict]) -> CachedPayload:
    """
    Buat CachedPayload dengan TTL adaptif berdasarkan URL expiry terpendek.
    Mencegah serving source yang sudah expired.
    """
    now = time.time()
    min_expiry = now + Config.L2_FALLBACK_TTL

    for src in sources:
        raw_url = src.get("raw_url") or src.get("url", "")
        if raw_url and ("workers.dev" not in raw_url) and ("tg-proxy" not in raw_url):
            candidate = extract_url_expiry(raw_url)
            if candidate < min_expiry:
                min_expiry = candidate

    # Beri buffer 5 menit sebelum actual expiry untuk safety margin
    safe_expiry = max(now + 600, min_expiry - 300)
    stale_at    = now + Config.L1_FRESH_TTL

    # stale_at tidak boleh melewati expires_at
    if stale_at > safe_expiry:
        stale_at = safe_expiry - 60

    return CachedPayload(
        sources    = sources,
        downloads  = downloads,
        created_at = now,
        expires_at = safe_expiry,
        stale_at   = stale_at,
    )


# ══════════════════════════════════════════════════════════════════════════════
# § 7. LIVE SCRAPER WRAPPER
# ══════════════════════════════════════════════════════════════════════════════

QUALITY_RANK = Config.QUALITY_RANK


async def _live_scrape(episode_url: str, provider_id: str) -> Optional[CachedPayload]:
    """
    Panggil provider scraper → ekstrak raw video → buat CachedPayload.
    Ini adalah L3, hanya dipanggil saat cache miss total.
    """
    provider = Config.PROVIDERS.get(provider_id)
    if not provider:
        return None

    raw_result = await provider.get_episode_sources(episode_url)

    if isinstance(raw_result, list):
        raw_sources, downloads = raw_result, []
    else:
        raw_sources = raw_result.get("sources", [])
        downloads   = raw_result.get("downloads", [])

    if not raw_sources:
        return None

    sem = asyncio.Semaphore(4)

    async def resolve_one(src: dict) -> Optional[dict]:
        raw_url = src.get("url") or src.get("resolved", "")
        if not raw_url:
            return None
        async with sem:
            try:
                async with asyncio.timeout(7.0):
                    resolved = await extractor.extract_raw_video(raw_url)
            except Exception:
                return None

        resolved_lower = resolved.lower()
        is_direct = (
            any(resolved.split("?")[0].endswith(ext) for ext in (".m3u8", ".mp4", ".webm"))
            or "googlevideo.com/videoplayback" in resolved_lower
            or "kuroplayer.xyz"               in resolved_lower
            or ".mp4"                         in resolved_lower
            or ".m3u8"                        in resolved_lower
        )
        video_type = (
            "hls" if ".m3u8" in resolved_lower
            else ("mp4" if is_direct else "iframe")
        )
        final_url = resolved if is_direct else raw_url

        return {
            "provider": src.get("provider") or provider_id,
            "quality":  src.get("quality", "Auto"),
            "url":      final_url,
            "raw_url":  resolved if is_direct else raw_url,
            "type":     video_type,
            "source":   provider_id,
        }

    resolved_list = await asyncio.gather(*(resolve_one(s) for s in raw_sources))
    final_sources = [s for s in resolved_list if s is not None]

    if not final_sources:
        return None

    # Sort: quality descending, direct sebelum iframe
    def _sort_key(s: dict) -> tuple:
        q = QUALITY_RANK.get(s.get("quality", "Auto"), 1)
        t = 1 if s.get("type") in ("hls", "mp4", "direct") else 0
        return (q, t)

    final_sources.sort(key=_sort_key, reverse=True)

    try:
        from utils.signed_url import sign_stream_url
        for source in final_sources:
            if source.get("type") in ("hls", "mp4", "direct"):
                raw_url = source.get("raw_url") or source.get("url")
                if raw_url and "workers.dev" not in raw_url and "tg-proxy" not in raw_url:
                    # Let's wrap it in our Cloudflare proxy
                    provider_for_proxy = "mp4upload" if "mp4upload" in raw_url else provider_id
                    source["raw_url"] = raw_url
                    source["url"] = sign_stream_url(raw_url, provider_for_proxy, source["quality"])
                    source["proxied"] = True
    except Exception as e:
        logger.warning(f"Error wrapping signed url in stream_cache: {e}")

    return build_cached_payload(final_sources, downloads)


# ══════════════════════════════════════════════════════════════════════════════
# § 8. WRITE-THROUGH PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

async def _write_l1(key: str, payload: CachedPayload) -> None:
    """Tulis ke Upstash Redis dengan TTL = expires_at - now."""
    ttl = max(300, int(payload.expires_at - time.time()))
    try:
        await upstash_set(key, payload.to_redis(), ex=ttl)
    except Exception as e:
        logger.warning(f"[L1 Write] {key}: {e}")


async def _write_l2(episode_url: str, provider_id: str, payload: CachedPayload) -> None:
    """Tulis ke Neon Postgres (video_cache table)."""
    from datetime import datetime, timedelta
    ttl_seconds = max(300, int(payload.expires_at - time.time()))
    expires_dt  = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    try:
        await database.execute(
            """
            INSERT INTO video_cache ("episodeUrl", "providerId", payload, "expiresAt", "updatedAt")
            VALUES (:url, :pid, :payload, :expires, NOW())
            ON CONFLICT ("episodeUrl")
            DO UPDATE SET
                payload     = EXCLUDED.payload,
                "expiresAt" = EXCLUDED."expiresAt",
                "updatedAt" = NOW()
            """,
            values={
                "url":     episode_url,
                "pid":     provider_id,
                "payload": json.dumps(payload.to_redis()),
                "expires": expires_dt,
            },
        )
    except Exception as e:
        logger.warning(f"[L2 Write] {episode_url}: {e}")


async def _write_all(episode_url: str, provider_id: str, payload: CachedPayload) -> None:
    """Fan-out write ke L1 + L2 secara concurrent."""
    key = CacheKey.stream(episode_url)
    await asyncio.gather(
        _write_l1(key, payload),
        _write_l2(episode_url, provider_id, payload),
        return_exceptions=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# § 9. THE ENGINE — Core Get Logic
# ══════════════════════════════════════════════════════════════════════════════

class StreamCacheEngine:
    """
    Singleton engine. Instansiasi satu kali di startup, gunakan di mana saja.

    Usage:
        engine = StreamCacheEngine()

        # Dalam route handler:
        result = await engine.get_stream(episode_url, provider_id)

        # Warmup background prefetch setelah user request episode N:
        asyncio.create_task(
            engine.prefetch_next(anilist_id, episode_number, all_episode_rows)
        )
    """

    def __init__(self) -> None:
        self._l0    = LRUCache(Config.L0_MAX_ENTRIES, Config.L0_TTL_SECONDS)
        self._cbs   = {pid: CircuitBreaker(pid) for pid in Config.PROVIDERS}
        self._inflight: dict[str, asyncio.Future] = {}  # dedup in-flight scrapes
        self._inflight_lock = asyncio.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_stream(
        self,
        episode_url: str,
        provider_id: str,
    ) -> dict:
        """
        Utama: kembalikan stream sources dengan latency serendah mungkin.

        Returns:
            {"sources": [...], "downloads": [...], "cache_layer": "L0|L1|L2|L3", "latency_ms": N}
        """
        t0 = time.monotonic()

        # ── L0: In-process LRU (0ms) ─────────────────────────────────────────
        key = CacheKey.stream(episode_url)
        l0_hit = await self._l0.get(key)
        if l0_hit and l0_hit.is_usable():
            if not l0_hit.is_fresh() and not l0_hit.should_early_refresh():
                # SWR: kick off background revalidation, serve stale
                asyncio.create_task(
                    self._background_revalidate(episode_url, provider_id, key)
                )
            return self._hit(l0_hit, "L0", t0)

        # ── L1: Upstash Redis (1–5ms) ─────────────────────────────────────────
        try:
            redis_data = await upstash_get(key)
            if redis_data and isinstance(redis_data, dict) and "sources" in redis_data:
                payload = CachedPayload.from_redis(redis_data)
                if payload.is_usable():
                    # Promote to L0
                    await self._l0.set(key, payload)
                    if not payload.is_fresh() or payload.should_early_refresh():
                        asyncio.create_task(
                            self._background_revalidate(episode_url, provider_id, key)
                        )
                    return self._hit(payload, "L1", t0)
        except Exception as e:
            logger.warning(f"[L1 Read] {key}: {e}")

        # ── L2: Neon Postgres (10–30ms) ───────────────────────────────────────
        try:
            row = await database.fetch_one(
                'SELECT payload FROM video_cache WHERE "episodeUrl" = :url AND "expiresAt" > NOW()',
                values={"url": episode_url},
            )
            if row and row["payload"]:
                raw = row["payload"]
                parsed = raw if isinstance(raw, dict) else json.loads(raw)
                payload = CachedPayload.from_redis(parsed)
                if payload.is_usable():
                    # Promote to L0 + L1
                    await asyncio.gather(
                        self._l0.set(key, payload),
                        _write_l1(key, payload),
                        return_exceptions=True,
                    )
                    if not payload.is_fresh() or payload.should_early_refresh():
                        asyncio.create_task(
                            self._background_revalidate(episode_url, provider_id, key)
                        )
                    return self._hit(payload, "L2", t0)
        except Exception as e:
            logger.warning(f"[L2 Read] {episode_url}: {e}")

        # ── L3: Live Scrape (2000–8000ms) ─────────────────────────────────────
        payload = await self._coalesced_scrape(episode_url, provider_id)
        if payload:
            # Write-through ke semua layer
            asyncio.create_task(_write_all(episode_url, provider_id, payload))
            await self._l0.set(key, payload)
            return self._hit(payload, "L3", t0)

        return {"sources": [], "downloads": [], "cache_layer": "MISS", "latency_ms": self._ms(t0)}

    async def invalidate(self, episode_url: str) -> None:
        """Hapus dari semua layer. Panggil setelah ingestion ke Telegram selesai."""
        key = CacheKey.stream(episode_url)
        await asyncio.gather(
            self._l0.delete(key),
            upstash_del(key),
            database.execute(
                'DELETE FROM video_cache WHERE "episodeUrl" = :url',
                values={"url": episode_url},
            ),
            return_exceptions=True,
        )
        logger.info(f"[Invalidate] Cleared all layers for {episode_url}")

    async def prefetch_next(
        self,
        anilist_id: int,
        current_ep: float,
        all_episodes: list[dict],
    ) -> None:
        """
        Background prefetch N episode berikutnya.
        Dipanggil sebagai fire-and-forget task setelah user request suatu episode.

        Args:
            all_episodes: list dari DB row dengan keys: episodeNumber, episodeUrl, providerId
        """
        sorted_eps = sorted(all_episodes, key=lambda e: e["episodeNumber"])
        # Temukan index episode saat ini
        current_idx = next(
            (i for i, e in enumerate(sorted_eps) if e["episodeNumber"] == current_ep),
            None,
        )
        if current_idx is None:
            return

        lookahead = sorted_eps[current_idx + 1: current_idx + 1 + Config.PREFETCH_LOOKAHEAD]

        for ep in lookahead:
            ep_url     = ep.get("episodeUrl", "")
            ep_num     = ep.get("episodeNumber")
            provider   = ep.get("providerId", "samehadaku")
            cache_key  = CacheKey.stream(ep_url)

            # Jangan prefetch jika sudah ada di L0
            if await self._l0.get(cache_key):
                continue

            # Tandai sebagai scheduled agar tidak duplikat
            sched_key = CacheKey.prefetch_scheduled(anilist_id, ep_num)
            already_sched = await upstash_get(sched_key)
            if already_sched:
                continue
            await upstash_set(sched_key, {"status": "prefetching"}, ex=1800)

            logger.info(f"[Prefetch] Queueing ep {ep_num} of anilist_id={anilist_id}")
            asyncio.create_task(self._do_prefetch(ep_url, provider, sched_key))
            await asyncio.sleep(Config.PREFETCH_DELAY)  # gentle rate limiting

    async def warmup_from_db(self, limit: int = 100) -> int:
        """
        Startup warmup: muat video_cache entries yang paling sering diakses ke L0.
        Panggil sekali dari lifespan() setelah DB connect.

        Returns jumlah entries yang dipanaskan.
        """
        try:
            rows = await database.fetch_all(
                """
                SELECT "episodeUrl", "providerId", payload
                FROM video_cache
                WHERE "expiresAt" > NOW()
                ORDER BY "updatedAt" DESC
                LIMIT :lim
                """,
                values={"lim": limit},
            )
            count = 0
            for row in rows:
                if not row["payload"]:
                    continue
                try:
                    raw     = row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"])
                    payload = CachedPayload.from_redis(raw)
                    if payload.is_usable():
                        key = CacheKey.stream(row["episodeUrl"])
                        await self._l0.set(key, payload)
                        count += 1
                except Exception:
                    continue
            logger.info(f"[Warmup] Loaded {count} entries into L0 LRU")
            return count
        except Exception as e:
            logger.error(f"[Warmup] Failed: {e}")
            return 0

    async def stats(self) -> dict:
        """Kembalikan snapshot kesehatan engine untuk monitoring / debug endpoint."""
        try:
            pg_total = await database.fetch_one(
                "SELECT COUNT(*) AS cnt FROM video_cache WHERE \"expiresAt\" > NOW()"
            )
            pg_count = pg_total["cnt"] if pg_total else 0
        except Exception:
            pg_count = -1

        return {
            "l0_entries":   self._l0.size,
            "l0_max":       Config.L0_MAX_ENTRIES,
            "l2_pg_entries": pg_count,
            "circuit_breakers": {
                pid: cb._state.value for pid, cb in self._cbs.items()
            },
            "inflight_scrapes": len(self._inflight),
        }

    # ── Private Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _hit(payload: CachedPayload, layer: str, t0: float) -> dict:
        return {
            **payload.to_response(),
            "cache_layer": layer,
            "latency_ms":  StreamCacheEngine._ms(t0),
        }

    @staticmethod
    def _ms(t0: float) -> int:
        return int((time.monotonic() - t0) * 1000)

    async def _coalesced_scrape(
        self,
        episode_url: str,
        provider_id: str,
    ) -> Optional[CachedPayload]:
        """
        Request coalescing: jika dua request datang untuk URL yang sama secara
        bersamaan, hanya satu scrape yang berjalan; yang lain menunggu hasilnya.

        Ini mencegah "thundering herd" saat L3 scrape sedang berjalan.
        """
        key = episode_url  # gunakan full URL sebagai dedup key

        async with self._inflight_lock:
            if key in self._inflight:
                fut = self._inflight[key]
                is_new = False
            else:
                fut = asyncio.get_event_loop().create_future()
                self._inflight[key] = fut
                is_new = True

        if not is_new:
            # Tunggu hasil dari scrape yang sedang berjalan
            logger.debug(f"[Coalesce] Waiting for in-flight scrape: {episode_url}")
            try:
                return await asyncio.wait_for(asyncio.shield(fut), timeout=20.0)
            except asyncio.TimeoutError:
                return None

        # Ini request pertama — jalankan scrape dengan Redis lock
        try:
            result = await self._locked_scrape(episode_url, provider_id)
            fut.set_result(result)
            return result
        except Exception as e:
            fut.set_exception(e)
            return None
        finally:
            async with self._inflight_lock:
                self._inflight.pop(key, None)

    async def _locked_scrape(
        self,
        episode_url: str,
        provider_id: str,
    ) -> Optional[CachedPayload]:
        """
        Scrape dengan Redis distributed lock — mencegah scrape redundan
        dari multiple HF Space instances (jika di-scale).
        """
        lock_key = CacheKey.lock(episode_url)

        # Coba ambil lock (NX = set if not exists)
        got_lock = await upstash_set(
            lock_key,
            {"worker": "local", "ts": time.time()},
            ex=Config.L1_LOCK_TTL,
            nx=True,
        )

        if not got_lock:
            # Instance lain sedang scraping — tunggu hasil dari L1
            logger.info(f"[Lock] Another instance scraping {episode_url}, polling L1...")
            for _ in range(12):  # poll up to 60 detik
                await asyncio.sleep(5)
                redis_data = await upstash_get(CacheKey.stream(episode_url))
                if redis_data and isinstance(redis_data, dict) and redis_data.get("sources"):
                    return CachedPayload.from_redis(redis_data)
            return None  # timeout, return miss

        try:
            cb = self._cbs.get(provider_id)
            if cb and not cb.is_allowed():
                logger.warning(f"[CB] {provider_id} is OPEN, skipping scrape")
                await upstash_del(lock_key)
                # Coba fallback ke provider prioritas berikutnya
                return await self._fallback_scrape(episode_url, provider_id)

            payload = await _live_scrape(episode_url, provider_id)
            if cb:
                if payload:
                    cb.record_success()
                else:
                    cb.record_failure()
            return payload
        finally:
            # Lepas lock
            await upstash_del(lock_key)

    async def _fallback_scrape(
        self,
        episode_url: str,
        failed_provider: str,
    ) -> Optional[CachedPayload]:
        """
        Coba provider lain berdasarkan prioritas jika provider utama circuit-open.
        Ini memerlukan lookup DB untuk episode yang sama dari provider berbeda.
        """
        try:
            rows = await database.fetch_all(
                """
                SELECT "episodeUrl", "providerId"
                FROM episodes
                WHERE "anilistId" = (
                    SELECT "anilistId" FROM episodes WHERE "episodeUrl" = :url LIMIT 1
                )
                AND "episodeNumber" = (
                    SELECT "episodeNumber" FROM episodes WHERE "episodeUrl" = :url LIMIT 1
                )
                AND "providerId" != :failed
                ORDER BY
                    CASE "providerId"
                     WHEN 'kuronime'   THEN 1
                     WHEN 'samehadaku' THEN 2
                     WHEN 'oploverz'   THEN 3
                     WHEN 'doronime'   THEN 4
                     WHEN 'otakudesu'  THEN 5
                     ELSE 6
                    END ASC
                LIMIT 3
                """,
                values={"url": episode_url, "failed": failed_provider},
            )
            for row in rows:
                alt_provider = row["providerId"]
                alt_url      = row["episodeUrl"]
                alt_cb       = self._cbs.get(alt_provider)
                if alt_cb and not alt_cb.is_allowed():
                    continue
                logger.info(f"[Fallback] Trying {alt_provider} for {episode_url}")
                result = await _live_scrape(alt_url, alt_provider)
                if result:
                    if alt_cb:
                        alt_cb.record_success()
                    return result
                if alt_cb:
                    alt_cb.record_failure()
        except Exception as e:
            logger.error(f"[Fallback] Error: {e}")
        return None

    async def _background_revalidate(
        self,
        episode_url: str,
        provider_id: str,
        cache_key: str,
    ) -> None:
        """
        SWR background refresh. Dipanggil sebagai asyncio.create_task.
        Scrape fresh, update semua layer tanpa memblokir response.
        """
        logger.debug(f"[SWR] Background revalidating {episode_url}")
        try:
            payload = await _live_scrape(episode_url, provider_id)
            if payload:
                await asyncio.gather(
                    self._l0.set(cache_key, payload),
                    _write_l1(cache_key, payload),
                    _write_l2(episode_url, provider_id, payload),
                    return_exceptions=True,
                )
                logger.info(f"[SWR] Revalidated {episode_url} — new expiry in {int(payload.expires_at - time.time())}s")
        except Exception as e:
            logger.warning(f"[SWR] Revalidation failed for {episode_url}: {e}")

    async def _do_prefetch(
        self,
        episode_url: str,
        provider_id: str,
        sched_key: str,
    ) -> None:
        """
        Jalankan prefetch untuk satu episode. Hapus scheduled marker setelah selesai.
        """
        try:
            payload = await self._coalesced_scrape(episode_url, provider_id)
            if payload:
                key = CacheKey.stream(episode_url)
                await asyncio.gather(
                    self._l0.set(key, payload),
                    _write_all(episode_url, provider_id, payload),
                    return_exceptions=True,
                )
                logger.info(f"[Prefetch] Done → {episode_url}")
        except Exception as e:
            logger.warning(f"[Prefetch] Failed: {e}")
        finally:
            await upstash_del(sched_key)


# ══════════════════════════════════════════════════════════════════════════════
# § 10. SINGLETON + FASTAPI INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

# Satu instance global — diinit di app startup
stream_cache = StreamCacheEngine()


# ── Drop-in untuk pipeline.py get_episode_stream() ───────────────────────────

async def get_cached_stream(
    anilist_id: int,
    ep_num: float,
) -> Optional[dict]:
    """
    Drop-in pengganti pipeline.get_episode_stream().
    Tambahkan ke main.py lifespan warmup dengan memanggil
    stream_cache.warmup_from_db() setelah DB connect.
    """
    # Tier 0: Telegram Swarm Storage (URL sudah di-ingest)
    try:
        row = await database.fetch_one(
            """
            SELECT id, "episodeUrl", "providerId"
            FROM   episodes
            WHERE  "anilistId" = :aid AND "episodeNumber" = :ep
            AND ("episodeUrl" LIKE '%tg-proxy%' OR "episodeUrl" LIKE '%workers.dev%')
            LIMIT 1
            """,
            values={"aid": anilist_id, "ep": ep_num},
        )
        if row:
            ep_url = row["episodeUrl"]
            return {
                "sources": [{
                    "provider": "Swarm Storage (Telegram)",
                    "quality":  "1080p",
                    "url":      ep_url,
                    "type":     "hls" if ("tg-proxy" in ep_url or ep_url.endswith(".m3u8")) else "mp4",
                    "source":   "telegram_swarm",
                }],
                "downloads":   [],
                "cache_layer": "L0-Telegram",
                "latency_ms":  0,
            }
    except Exception:
        pass

    # Ambil semua candidate episodes dari DB, sorted by provider priority
    rows = await database.fetch_all(
        """
        SELECT id, "episodeUrl", "providerId", "episodeNumber"
        FROM   episodes
        WHERE  "anilistId" = :aid AND "episodeNumber" = :ep
        ORDER BY
            CASE "providerId"
             WHEN 'kuronime'   THEN 1
             WHEN 'samehadaku' THEN 2
             WHEN 'oploverz'   THEN 3
             WHEN 'doronime'   THEN 4
             WHEN 'otakudesu'  THEN 5
             ELSE 6
            END ASC
        """,
        values={"aid": anilist_id, "ep": ep_num},
    )
    if not rows:
        return None

    for row in rows:
        result = await stream_cache.get_stream(row["episodeUrl"], row["providerId"])
        if result.get("sources"):
            result["episodeUrl"]  = row["episodeUrl"]
            result["usedProvider"] = row["providerId"]

            # Trigger ingestion ke Telegram jika ada direct link (fire-and-forget)
            direct = [s for s in result["sources"] if s.get("type") in ("hls", "mp4", "direct")]
            if direct:
                raw_url = direct[0].get("raw_url") or direct[0].get("url", "")
                if raw_url and "workers.dev" not in raw_url and "tg-proxy" not in raw_url:
                    from services.queue import enqueue_ingest_batch
                    asyncio.create_task(enqueue_ingest_batch())

            # Kick off prefetch untuk episode berikutnya (semua episodes list)
            asyncio.create_task(
                stream_cache.prefetch_next(anilist_id, ep_num, [dict(r) for r in rows])
            )

            return result

    return {"sources": [], "downloads": [], "error": "No sources resolved from any provider"}


# ── Debug / Admin Endpoint ────────────────────────────────────────────────────

async def cache_stats_handler() -> dict:
    """
    Tambahkan sebagai route di main.py:
        @app.get("/api/v2/admin/cache-stats", dependencies=[Depends(verify_admin_key)])
        async def cache_stats():
            return await cache_stats_handler()
    """
    return await stream_cache.stats()
