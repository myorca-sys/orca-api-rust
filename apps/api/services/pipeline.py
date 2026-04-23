"""
pipeline.py — Central data pipeline for the anime platform.

Responsibilities
----------------
1. sync_anime_episodes(anilist_id)
   Walk all provider mappings for an anime, scrape episode lists, and upsert
   into the `episodes` table.  Run this once per day per anime (or on-demand
   when a user hits a detail page that has no episodes yet).

2. resolve_episode_sources(episode_url, provider_id)
   Turn a provider episode page URL into a list of raw playable video URLs.
   Results are cached in `video_cache` with a 6-hour TTL so re-plays are fast.

3. get_anime_detail(anilist_id)
   Return anime metadata + a clean, de-duplicated, sorted episode list from DB.

4. get_episode_stream(anilist_id, ep_num)
   Find the best provider episode for this anilist_id+ep_num combo, resolve
   sources (using cache when possible), and return them ready for the player.
"""

import asyncio
import json
import re
import urllib.parse
import time
from datetime import datetime, timedelta
from typing import Optional

from db.connection import database
from utils.distributed_lock import DistributedLock
from services.cache import upstash_get, upstash_set, upstash_del
from services.providers import (
    oploverz_provider,
    otakudesu_provider,
    samehadaku_provider,
    doronime_provider,
    kuronime_provider,
    extractor,
)

# ── provider registry ──────────────────────────────────────────────────────────

PROVIDERS = {
    "oploverz":   oploverz_provider,
    "otakudesu":  otakudesu_provider,
    "samehadaku": samehadaku_provider,
    "doronime":   doronime_provider,
    "kuronime":   kuronime_provider,
}

# Priority when multiple providers have the same episode.
# Lower number = higher priority.
PROVIDER_PRIORITY = {"kuronime": 1, "samehadaku": 2, "oploverz": 3, "doronime": 4, "otakudesu": 5}

SOURCE_CACHE_HOURS = 6

# ── helpers ────────────────────────────────────────────────────────────────────

def extract_episode_number(title: str) -> Optional[float]:
    """
    Parse episode number from strings like:
      'Episode 12', 'Eps 12.5', 'OVA 1', 'Specials 1', '1', 'Ep.12'
    Returns float or None.
    """
    if not title:
        return None
    # Named pattern: Episode / Eps / Ep + number
    m = re.search(r"(?:episode|eps?)[.\s]*(\d+(?:[.,]\d+)?)", title, re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    # OVA / Special / Movie: treat as 0.5, 0.6, etc. (won't conflict with regular eps)
    if re.search(r"\b(ova|specials?|movie)\b", title, re.IGNORECASE):
        m2 = re.search(r"(\d+)", title)
        return float(f"0.{m2.group(1)}") if m2 else 0.0
    # Bare number at the start or end
    m3 = re.search(r"^\s*(\d+(?:[.,]\d+)?)\s*$", title.strip())
    if m3:
        return float(m3.group(1).replace(",", "."))
    return None


def build_provider_series_url(provider_id: str, provider_slug: str) -> str:
    """Build the series page URL for a given provider + slug."""
    bases = {
        "oploverz":  "https://o.oploverz.ltd/series/{slug}/",
        "otakudesu": "https://otakudesu.blog/anime/{slug}/",
        "samehadaku": "https://v2.samehadaku.how/anime/{slug}/",
        "doronime":  "https://doronime.id/{slug}/",
        "kuronime": "https://kuronime.sbs/anime/{slug}/",
    }
    template = bases.get(provider_id, "")
    return template.format(slug=provider_slug) if template else ""


def extract_url_expiry(url: str) -> int:
    """Extract expiry dari URL parameter jika ada."""
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    
    if 'expires' in params:
        return int(params['expires'][0])
    if 'expire' in params:
        return int(params['expire'][0])
    
    # Default 4 jam (konservatif)
    return int(time.time()) + 4 * 3600

# ── DB helpers ─────────────────────────────────────────────────────────────────

async def get_provider_mappings(anilist_id: int) -> dict:
    """Return {providerId: providerSlug} for every known provider of this anime."""
    rows = await database.fetch_all(
        'SELECT "providerId", "providerSlug" FROM anime_mappings WHERE "anilistId" = :id',
        values={"id": anilist_id},
    )
    return {r["providerId"]: r["providerSlug"] for r in rows}


async def upsert_episode(
    anilist_id: int,
    provider_id: str,
    ep_num: float,
    ep_url: str,
    ep_title: Optional[str] = None,
    thumbnail: Optional[str] = None,
) -> None:
    await database.execute(
        """
        INSERT INTO episodes
            ("anilistId", "providerId", "episodeNumber", "episodeTitle", "episodeUrl", "thumbnailUrl", "updatedAt")
        VALUES
            (:anilist_id, :provider_id, :ep_num, :ep_title, :ep_url, :thumbnail, NOW())
        ON CONFLICT ("anilistId", "providerId", "episodeNumber")
        DO UPDATE SET
            "episodeUrl"   = CASE 
                                WHEN episodes."episodeUrl" LIKE '%tg-proxy%' AND EXCLUDED."episodeUrl" NOT LIKE '%tg-proxy%' 
                                THEN episodes."episodeUrl"
                                ELSE EXCLUDED."episodeUrl"
                             END,
            "episodeTitle" = EXCLUDED."episodeTitle",
            "thumbnailUrl" = COALESCE(EXCLUDED."thumbnailUrl", episodes."thumbnailUrl"),
            "updatedAt"    = NOW()
        """,
        values={
            "anilist_id": anilist_id,
            "provider_id": provider_id,
            "ep_num": ep_num,
            "ep_title": ep_title,
            "ep_url": ep_url,
            "thumbnail": thumbnail,
        },
    )


async def get_video_cache(episode_url: str) -> Optional[dict]:
    # 1. Try Redis first (hot cache)
    redis_key = f"video_cache:{episode_url}"
    cached_redis = await upstash_get(redis_key)
    if cached_redis:
        return cached_redis

    # 2. Fallback to Postgres
    row = await database.fetch_one(
        'SELECT payload FROM video_cache WHERE "episodeUrl" = :url AND "expiresAt" > NOW()',
        values={"url": episode_url},
    )
    if row and row["payload"]:
        raw = row["payload"]
        parsed = raw if isinstance(raw, dict) else json.loads(raw)
        # Restore to redis
        await upstash_set(redis_key, parsed, ex=SOURCE_CACHE_HOURS * 3600)
        return parsed
    return None


async def save_video_cache(episode_url: str, provider_id: str, payload: dict) -> None:
    # Get actual expiry based on best source URL if available
    best_source_url = ""
    if payload.get("sources"):
        best_source_url = payload["sources"][0].get("raw_url") or payload["sources"][0].get("url")
    
    actual_expiry = extract_url_expiry(best_source_url) if best_source_url else int(time.time()) + 4 * 3600
    ttl_seconds = max(3600, actual_expiry - int(time.time()))

    # 1. Save to Redis (hot cache)
    redis_key = f"video_cache:{episode_url}"
    await upstash_set(redis_key, payload, ex=ttl_seconds)

    # 2. Save to Postgres
    expires = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    await database.execute(
        """
        INSERT INTO video_cache ("episodeUrl", "providerId", payload, "expiresAt", "updatedAt")
        VALUES (:url, :provider_id, :payload, :expires, NOW())
        ON CONFLICT ("episodeUrl")
        DO UPDATE SET
            payload     = EXCLUDED.payload,
            "expiresAt" = EXCLUDED."expiresAt",
            "updatedAt" = NOW()
        """,
        values={
            "url": episode_url,
            "provider_id": provider_id,
            "payload": json.dumps(payload),
            "expires": expires,
        },
    )


# ── core pipeline functions ────────────────────────────────────────────────────

async def sync_anime_episodes(anilist_id: int) -> dict:
    """
    Fetch episode lists from all known providers for this anime and store them.
    Returns {"synced": N, "providers": [...], "errors": [...]}
    """
    mappings = await get_provider_mappings(anilist_id)
    if not mappings:
        return {"synced": 0, "providers": [], "errors": ["No provider mappings found"]}

    synced_total = 0
    providers_done = []
    errors = []

    lock = DistributedLock(
        upstash_get_fn=upstash_get,
        upstash_set_fn=upstash_set,
        upstash_del_fn=upstash_del,
        key=f"sync_anime:{anilist_id}",
        ttl=120
    )

    try:
        async with lock:
            for provider_id, provider_slug in mappings.items():
                provider = PROVIDERS.get(provider_id)
                if not provider:
                    errors.append(f"Unknown provider: {provider_id}")
                    continue

                series_url = build_provider_series_url(provider_id, provider_slug)
                if not series_url:
                    errors.append(f"Cannot build URL for {provider_id}")
                    continue

                try:
                    detail = await provider.get_anime_detail(series_url)
                    raw_episodes = detail.get("episodes", [])
                    print(f"[Pipeline Debug] Fetched {len(raw_episodes)} episodes from {series_url}")
                    
                    # Domain 1: Record Metadata Source
                    try:
                        from services.reconciler import reconciler
                        canonical_row = await database.fetch_one(
                            "SELECT id, episode_count_actual, air_schedule_wib, genres_local FROM canonical_anime WHERE anilist_id = :id",
                            {"id": anilist_id}
                        )
                        if canonical_row:
                            canonical_id = canonical_row["id"]
                            current_actual = canonical_row["episode_count_actual"]
                            fetched_count = detail.get("total_episodes") or len(raw_episodes)
                            
                            # 1. Episode Count
                            await reconciler.record_metadata_source(
                                canonical_id=canonical_id,
                                source_name=f"{provider_id}_scrape",
                                field_name="episode_count",
                                raw_value=str(fetched_count),
                                confidence=0.9
                            )
                            if current_actual is None or fetched_count > current_actual:
                                await database.execute(
                                    "UPDATE canonical_anime SET episode_count_actual = :cnt, last_reconciled_at = NOW() WHERE id = :cid",
                                    {"cnt": fetched_count, "cid": canonical_id}
                                )
                                
                            # 2. Air Schedule (Jadwal Tayang)
                            air_day = detail.get("air_day")
                            if air_day:
                                await reconciler.record_metadata_source(
                                    canonical_id=canonical_id,
                                    source_name=f"{provider_id}_scrape",
                                    field_name="air_schedule_wib",
                                    raw_value=air_day,
                                    confidence=0.85
                                )
                                # Provider wins if current is null or empty
                                if not canonical_row["air_schedule_wib"]:
                                    await database.execute(
                                        "UPDATE canonical_anime SET air_schedule_wib = :air_day, last_reconciled_at = NOW() WHERE id = :cid",
                                        {"air_day": air_day, "cid": canonical_id}
                                    )
                                    
                            # 3. Genres Local
                            genres_local = detail.get("genres_local")
                            if genres_local and isinstance(genres_local, list) and len(genres_local) > 0:
                                import json
                                genres_json = json.dumps(genres_local)
                                await reconciler.record_metadata_source(
                                    canonical_id=canonical_id,
                                    source_name=f"{provider_id}_scrape",
                                    field_name="genres_local",
                                    raw_value=genres_json,
                                    confidence=0.85
                                )
                                # Provider wins if current is null or empty brackets
                                current_genres = canonical_row["genres_local"]
                                if not current_genres or current_genres == "[]" or current_genres == []:
                                    await database.execute(
                                        "UPDATE canonical_anime SET genres_local = :g, last_reconciled_at = NOW() WHERE id = :cid",
                                        {"g": genres_json, "cid": canonical_id}
                                    )
                                    
                            # 4. Score Local, Studio, Status Local, Views Local -> just record to metadata_sources for now
                            for field_name in ["score_local", "studio", "status_local", "views_local"]:
                                val = detail.get(field_name)
                                if val:
                                    await reconciler.record_metadata_source(
                                        canonical_id=canonical_id,
                                        source_name=f"{provider_id}_scrape",
                                        field_name=field_name,
                                        raw_value=str(val),
                                        confidence=0.85
                                    )
                                    
                    except Exception as e:
                        print(f"[Pipeline] Failed to record metadata source: {e}")

                    sem = asyncio.Semaphore(5)
                    count = 0

                    async def process_ep(ep: dict):
                        nonlocal count
                        ep_num = extract_episode_number(ep.get("title", ""))
                        if ep_num is None:
                            return
                        async with sem:
                            await upsert_episode(
                                anilist_id=anilist_id,
                                provider_id=provider_id,
                                ep_num=ep_num,
                                ep_url=ep["url"],
                                ep_title=ep.get("title"),
                                thumbnail=ep.get("thumbnail"),
                            )
                            count += 1

                    await asyncio.gather(*(process_ep(ep) for ep in raw_episodes))
                    synced_total += count
                    providers_done.append(provider_id)
                    print(f"[Pipeline] Synced {count} episodes from {provider_id} for anilist_id={anilist_id}")

                except Exception as e:
                    error_msg = f"{provider_id}: {str(e)}"
                    errors.append(error_msg)
                    print(f"[Pipeline] Sync error — {error_msg}")
    except TimeoutError:
        print(f"[Pipeline] Another sync is already in progress for anilist_id={anilist_id}")
        errors.append("Sync already in progress")

    return {"synced": synced_total, "providers": providers_done, "errors": errors}


async def resolve_episode_sources(episode_url: str, provider_id: str) -> dict:
    """
    Resolve a provider episode page URL to a list of playable video sources.

    Flow:
      1. Check video_cache table — return immediately if fresh.
      2. Call provider.get_episode_sources() to get raw embed/iframe URLs.
      3. Feed each raw URL through UniversalExtractor to get the actual .m3u8 / .mp4.
      4. Filter out anything that didn't resolve to a direct video URL.
      5. Sort by quality, persist to cache, and return.

    Returns:
      {"sources": [{provider, quality, url, type}], "downloads": [...]}
    """
    # 1. Cache hit
    cached = await get_video_cache(episode_url)
    if cached:
        print(f"[Pipeline] Cache hit for {episode_url}")
        return cached

    provider = PROVIDERS.get(provider_id)
    if not provider:
        return {"sources": [], "downloads": []}

    try:
        raw_result = await provider.get_episode_sources(episode_url)

        # Normalize: providers return either a list or {"sources": [...], "downloads": [...]}
        if isinstance(raw_result, list):
            raw_sources = raw_result
            downloads = []
        else:
            raw_sources = raw_result.get("sources", [])
            downloads = raw_result.get("downloads", [])

        if not raw_sources:
            return {"sources": [], "downloads": downloads}

        # 2-3. Resolve all sources concurrently (max 4 at a time)
        sem = asyncio.Semaphore(4)

        async def resolve_one(src: dict) -> Optional[dict]:
            raw_url = src.get("url") or src.get("resolved", "")
            if not raw_url:
                return None
            
            async with sem:
                resolved = await extractor.extract_raw_video(raw_url)

            # Accept as-is if it looks like a direct video already
            resolved_lower = resolved.lower()
            is_direct = (
                any(resolved.split("?")[0].endswith(ext) for ext in (".m3u8", ".mp4", ".webm"))
                or "googlevideo.com/videoplayback" in resolved_lower
                or "kuroplayer.xyz" in resolved_lower
                or ".mp4" in resolved_lower
                or ".m3u8" in resolved_lower
            )
            
            if not is_direct:
                video_type = "iframe"
                final_url = raw_url
            else:
                # Use HLS for .m3u8 or KuroPlayer, else MP4
                video_type = "hls" if (".m3u8" in resolved_lower or "kuroplayer" in resolved_lower) else "mp4"
                final_url = resolved

            return {
                "provider": src.get("provider") or src.get("domain") or provider_id,
                "quality":  src.get("quality", "Auto"),
                "url":      final_url,
                "type":     video_type,
                "source":   provider_id,
            }

        tasks = [resolve_one(s) for s in raw_sources]
        resolved_list = await asyncio.gather(*tasks)
        final_sources = [s for s in resolved_list if s is not None]

        # 4. Sort by quality
        quality_rank = {"1080p": 5, "720p": 4, "480p": 3, "360p": 2, "Auto": 1}
        final_sources.sort(key=lambda x: quality_rank.get(x["quality"], 0), reverse=True)

        from utils.signed_url import sign_stream_url
        for source in final_sources:
            if source.get("type") in ("hls", "mp4", "direct"):
                source["raw_url"] = source["url"]
                source["url"] = sign_stream_url(source["raw_url"], provider_id, source["quality"])
                source["proxied"] = True

        payload = {"sources": final_sources, "downloads": downloads}

        # 5. Cache
        if final_sources:
            await save_video_cache(episode_url, provider_id, payload)

        return payload

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Pipeline] resolve_episode_sources error for {episode_url}: {e}")
        return {"sources": [], "downloads": []}


async def get_anime_detail(anilist_id: int) -> Optional[dict]:
    """
    Return anime metadata from DB + a clean episode list.

    Episode list rules:
      - De-duplicated by episodeNumber — if multiple providers have ep 5,
        we pick the one with the highest provider priority (oploverz > otakudesu > …).
      - Sorted descending (newest first, like a normal anime site).
      - Each episode carries its provider so the stream endpoint knows which
        scraper to call.
    """
    meta = await database.fetch_one(
        '''
        SELECT m.*, 
               c.title_preferred as "canonicalTitle", 
               c.episode_count_actual as "canonicalEpisodes",
               c.genres_local as "canonicalGenres",
               c.air_schedule_wib as "canonicalSchedule"
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE m."anilistId" = :id
        ''',
        values={"id": anilist_id},
    )
    if not meta:
        return None

    # DISTINCT ON picks the first row per episodeNumber after ORDER BY priority
    eps = await database.fetch_all(
        """
        SELECT DISTINCT ON ("episodeNumber")
               "episodeNumber", "episodeTitle", "episodeUrl", "providerId", "thumbnailUrl"
        FROM   episodes
        WHERE  "anilistId" = :id
        ORDER  BY
               "episodeNumber" DESC,
               CASE "providerId"
                WHEN 'samehadaku' THEN 1
                WHEN 'kuronime'   THEN 1
                WHEN 'oploverz'   THEN 2
                WHEN 'doronime'   THEN 3
                WHEN 'otakudesu'  THEN 4
                ELSE 5
               END ASC
        """,
        values={"id": anilist_id},
    )

    meta_dict = dict(meta)
    
    # Override with canonical data if available
    if meta_dict.get("canonicalTitle"):
        meta_dict["cleanTitle"] = meta_dict["canonicalTitle"]
    if meta_dict.get("canonicalEpisodes"):
        meta_dict["totalEpisodes"] = meta_dict["canonicalEpisodes"]
    if meta_dict.get("canonicalGenres") and meta_dict.get("canonicalGenres") != "[]":
        meta_dict["genres"] = meta_dict["canonicalGenres"]
    if meta_dict.get("canonicalSchedule"):
        meta_dict["airSchedule"] = meta_dict["canonicalSchedule"]
    if meta_dict.get("localViews"):
        meta_dict["localViews"] = int(meta_dict["localViews"])
    if meta_dict.get("localScore"):
        val = float(meta_dict["localScore"])
        meta_dict["score"] = int(val * 10) if val <= 10 else int(val)
    if meta_dict.get("localStudio"):
        meta_dict["studios"] = [meta_dict["localStudio"]]
    if meta_dict.get("localStatus"):
        st = meta_dict["localStatus"].lower()
        meta_dict["status"] = 'FINISHED' if 'completed' in st or 'tamat' in st else 'RELEASING'
        
    # Remove temporary keys
    for key in ["canonicalTitle", "canonicalEpisodes", "canonicalGenres", "canonicalSchedule", "localScore", "localStudio", "localStatus"]:
        meta_dict.pop(key, None)
    
    # Parse JSON columns since they might be returned as strings
    import json
    for col in ["genres", "studios", "recommendations", "nextAiringEpisode"]:
        if col in meta_dict and isinstance(meta_dict[col], str):
            try:
                meta_dict[col] = json.loads(meta_dict[col])
            except Exception:
                pass

    return {
        **meta_dict,
        "episodes": [dict(e) for e in eps],
    }


async def get_episode_stream(anilist_id: int, ep_num: float) -> Optional[dict]:
    """
    Get playable sources for anilistId + episodeNumber using StreamCacheEngine.
    """
    from services.stream_cache import get_cached_stream
    return await get_cached_stream(anilist_id, ep_num)


async def ensure_episodes_exist(anilist_id: int) -> bool:
    """
    Check whether we have episodes in DB for this anime.
    If not, trigger a background sync via QStash to distribute scraping load,
    and return False immediately to avoid blocking the event loop.
    Returns True if episodes already exist.
    """
    count_row = await database.fetch_one(
        'SELECT COUNT(*) as cnt FROM episodes WHERE "anilistId" = :id',
        values={"id": anilist_id},
    )
    if count_row and count_row["cnt"] > 0:
        return True

    # No episodes — enqueue async sync task (Serverless Queue)
    print(f"[Pipeline] No episodes for anilist_id={anilist_id}, enqueuing to QStash…")
    from services.queue import enqueue_sync
    await enqueue_sync(anilist_id)
    return False
