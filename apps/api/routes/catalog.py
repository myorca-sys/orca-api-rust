"""
catalog.py — Clean v2 API that uses anilistId as the universal primary key.

Why v2?
  The v1 API (/api/scrape, /api/multi-source, etc.) mixed oploverz slugs with
  AniList IDs and scraped on-demand.  v2 always uses anilistId, reads structured
  data from the DB, and only hits provider sites when the cache is cold.

Endpoints
─────────
GET  /api/v2/anime/{anilist_id}
     Full anime detail + episode list.  Triggers a background sync if the
     episode list is empty so the next request will be fast.

GET  /api/v2/anime/{anilist_id}/episodes/{ep_num}/stream
     Returns playable video sources for a specific episode.
     Uses video_cache; re-scrapes only when cache is stale (> 6 hours).

POST /api/v2/anime/{anilist_id}/sync
     Manually trigger an episode sync.  Useful after a new season drops.

GET  /api/v2/search?q=...
     Search AniList and enrich with our DB mapping data.

GET  /api/v2/anime/{anilist_id}/episodes
     Just the episode list (lighter response for the episode-list component).
"""

import asyncio
import urllib.parse
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Response

from db.connection import database
from services.pipeline import (
    get_anime_detail,
    get_episode_stream,
    sync_anime_episodes,
    ensure_episodes_exist,
    get_provider_mappings,
)
from services.anilist import fetch_anilist_info, fetch_anilist_info_by_id
from services.db import upsert_anime_db
from services.cache import swr_cache_get

router = APIRouter()


@router.get("/v2/debug/kuronime")
async def debug_kuronime(url: str = Query(...)):
    from services.pipeline import resolve_episode_sources
    try:
        result = await resolve_episode_sources(url, "kuronime")
        return result
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()}

# ── GET /api/v2/anime/{anilist_id} ─────────────────────────────────────────────

@router.get("/v2/anime/{anilist_id}")
async def get_anime_v2(anilist_id: int, background_tasks: BackgroundTasks, response: Response):
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    try:
        """
        Full anime detail with episode list.
        """
        # Fetch from DB (fast path)
        data = await get_anime_detail(anilist_id)

        # Not in DB at all — try AniList
        if data is None:
            anilist_data = await _fetch_and_save_anilist(anilist_id)
            if not anilist_data:
                raise HTTPException(status_code=404, detail=f"Anime {anilist_id} not found on AniList")
            # Try DB again after saving
            data = await get_anime_detail(anilist_id)
            if data is None:
                raise HTTPException(status_code=404, detail="Anime saved but could not be read back")

        # Override nativeTitle with Romaji title directly from AniList 
        # so frontend displays alphabet characters instead of Japanese Kanji
        try:
            live_anilist = await fetch_anilist_info_by_id(anilist_id)
            if live_anilist and live_anilist.get('romajiTitle'):
                data['nativeTitle'] = live_anilist['romajiTitle']
        except:
            pass
            
        # Auto-translate synopsis to Indonesian and save to DB
        if data.get("synopsis"):
            try:
                from utils.translator import translate_en_to_id
                # Quick heuristic to avoid translating if it seems already translated
                if "dan" not in data["synopsis"].lower() and "yang" not in data["synopsis"].lower():
                    translated = await translate_en_to_id(data["synopsis"])
                    if translated and translated != data["synopsis"]:
                        data["synopsis"] = translated
                        background_tasks.add_task(
                            database.execute,
                            'UPDATE anime_metadata SET synopsis = :synopsis WHERE "anilistId" = :id',
                            values={"synopsis": translated, "id": anilist_id}
                        )
            except Exception as e:
                print(f"Translation error: {e}")

        # Episodes empty — sync in background so next request is fast
        if not data.get("episodes"):
            from services.queue import enqueue_sync
            await enqueue_sync(anilist_id)
            # Return metadata without episodes rather than a 404
            return {
                "success": True,
                "syncing": True,
                "message": "Episode list is being fetched. Please refresh in ~10 seconds.",
                "data": data,
            }

        return {"success": True, "data": data}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── GET /api/v2/anime/{anilist_id}/episodes ────────────────────────────────────

@router.get("/v2/anime/{anilist_id}/episodes")
async def get_episodes_v2(anilist_id: int, background_tasks: BackgroundTasks, response: Response):
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    """Lightweight endpoint: only the episode list."""
    has_eps = await ensure_episodes_exist(anilist_id)
    if not has_eps:
        # Kick off a sync via QStash task queue to distribute bots
        from services.queue import enqueue_sync
        await enqueue_sync(anilist_id)
        return {"success": False, "syncing": True, "data": []}

    rows = await database.fetch_all(
        """
        SELECT DISTINCT ON ("episodeNumber")
               "episodeNumber", "episodeTitle", "episodeUrl", "providerId", "thumbnailUrl"
        FROM   episodes
        WHERE  "anilistId" = :id
        ORDER  BY "episodeNumber" DESC,
               CASE "providerId" 
                 WHEN 'otakudesu' THEN 1 
                 WHEN 'samehadaku' THEN 2 
                 WHEN 'doronime' THEN 3 
                 WHEN 'oploverz' THEN 4 
                 ELSE 99 
               END
        """,
        values={"id": anilist_id},
    )
    return {"success": True, "data": [dict(r) for r in rows]}


# ── ADMIN ENDPOINTS ────────────────────────────────────────────────────────────

@router.get("/v2/admin/stats")
async def admin_get_stats():
    """Get ingestion and database stats for the admin dashboard"""
    from services.prefetch import get_ingestion_stats
    stats = await get_ingestion_stats()
    return {"success": True, **stats}

@router.post("/v2/admin/trigger-prefetch")
async def admin_trigger_prefetch():
    """Manually trigger the smart pre-fetch job instead of waiting for cron"""
    # Import here to avoid circular imports if any
    from services.prefetch import smart_prefetch_episodes
    import asyncio
    
    # We trigger it in the background so the request doesn't timeout
    asyncio.create_task(smart_prefetch_episodes())
    
    return {"success": True, "message": "Smart Pre-fetch job started in the background."}

@router.get("/v2/admin/database")
async def admin_get_database():
    """Return all anime in database with episode counts"""
    try:
        query = '''
            SELECT a."anilistId", a."cleanTitle" as title, a.genres, a.status, a.year, a."coverImage" as cover,
                   COUNT(e.id) as episode_count,
                   SUM(CASE WHEN e."episodeUrl" LIKE '%tg-proxy%' OR e."episodeUrl" LIKE '%workers.dev%' THEN 1 ELSE 0 END) as tg_count,
                   MAX(e."providerId") as "providerId"
            FROM anime_metadata a
            LEFT JOIN episodes e ON a."anilistId" = e."anilistId"
            GROUP BY a."anilistId", a."cleanTitle", a.genres, a.status, a.year, a."coverImage"
            ORDER BY a.year DESC, a."cleanTitle" ASC
        '''
        rows = await database.fetch_all(query)
        data = [dict(row) for row in rows]
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/v2/admin/mass-sync")
async def admin_mass_sync():
    """Trigger a mass sync via QStash or local background task"""
    import subprocess
    import os
    import sys
    script_path = os.path.join(os.path.dirname(__file__), "../scripts/mass_sync.py")
    env = os.environ.copy()
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    env["PYTHONPATH"] = f"{env.get('PYTHONPATH', '')}:{root_dir}:{os.path.join(root_dir, 'apps', 'api')}"
    subprocess.Popen([sys.executable, script_path], env=env)
    return {"success": True, "message": "Mass sync process started in background."}

@router.post("/v2/admin/sync-missing")
async def admin_sync_missing():
    """Find animes with 0 episodes and queue them for sync"""
    try:
        query = '''
            SELECT a."anilistId"
            FROM anime_metadata a
            LEFT JOIN episodes e ON a."anilistId" = e."anilistId"
            GROUP BY a."anilistId"
            HAVING COUNT(e.id) = 0
        '''
        rows = await database.fetch_all(query)
        count = 0
        for row in rows:
            await enqueue_sync(row["anilistId"])
            count += 1
            
        return {"success": True, "message": f"Queued {count} missing anime for syncing."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/v2/debug/curl")
async def debug_curl(url: str):
    from utils.tls_spoof import TLSSpoofTransport
    try:
        html = await TLSSpoofTransport.get(url)
        return {"success": True, "html_len": len(html), "html_snippet": html[:500]}
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}

@router.get("/v2/debug/stream")
async def debug_stream(anilist_id: int, title: str, ep: float):
    from routes.stream_v2 import _title_variants, _last_resort_otakudesu, _scrape_kuronime
    from services.anilist import fetch_anilist_info_by_id
    info = await fetch_anilist_info_by_id(anilist_id)
    variants = _title_variants(title, info)
    res_ota = await _last_resort_otakudesu(variants[0], ep)
    res_ota2 = await _last_resort_otakudesu(variants[1] if len(variants) > 1 else variants[0], ep)
    res_kur = await _scrape_kuronime(title, ep)
    return {
        "variants": variants,
        "otakudesu1": res_ota,
        "otakudesu2": res_ota2,
        "kuronime": res_kur
    }

@router.post("/v2/admin/fix-titles")
async def admin_fix_titles(background_tasks: BackgroundTasks):
    """Mass update nativeTitle to Romaji for all existing anime in the database"""
    async def _process_fix():
        try:
            from services.anilist import fetch_anilist_info_by_id
            rows = await database.fetch_all('SELECT "anilistId", "nativeTitle" FROM anime_metadata')
            count = 0
            for row in rows:
                aid = row["anilistId"]
                # Check if it contains non-ASCII characters (like Kanji/Kana)
                if any(ord(c) > 127 for c in row["nativeTitle"] or ""):
                    try:
                        info = await fetch_anilist_info_by_id(aid)
                        if info and info.get("romajiTitle"):
                            await database.execute(
                                'UPDATE anime_metadata SET "nativeTitle" = :romaji WHERE "anilistId" = :aid',
                                values={"romaji": info["romajiTitle"], "aid": aid}
                            )
                            count += 1
                    except Exception as e:
                        print(f"Error fixing {aid}: {e}")
                    await asyncio.sleep(0.35) # Avoid hitting AniList rate limits
            print(f"Successfully fixed {count} Japanese titles to Romaji in DB.")
        except Exception as e:
            print(f"Fatal error in fix-titles: {e}")

    background_tasks.add_task(_process_fix)
    return {"success": True, "message": "Background job started to fix Japanese titles to Romaji."}

@router.get("/v2/anime/{anilist_id}/episodes/{ep_num}/stream")
async def get_episode_stream_v2(
    anilist_id: int, 
    ep_num: str, 
    response: Response, 
    refresh: bool = Query(False)
):
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    """
    Return resolved video sources for one episode.

    ep_num can be "1", "12", "12.5" (floats for OVAs / specials).
    Sources come from video_cache when fresh; re-scrapes when stale.
    Set refresh=true to skip DB cache and force a new scrape.
    """
    try:
        ep_float = float(ep_num)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid episode number: {ep_num}")

    if refresh:
        # Get mapping first
        from services.pipeline import get_provider_mappings
        from services.cache import upstash_del
        from services.stream_cache import CacheKey
        mappings = await get_provider_mappings(anilist_id)
        for pid, slug in mappings.items():
            # Clear cache for all providers of this anime to force re-scrape
            from services.pipeline import build_provider_series_url
            series_url = build_provider_series_url(pid, slug)
            rows = await database.fetch_all(
                'SELECT "episodeUrl" FROM episodes WHERE "anilistId" = :aid AND "providerId" = :pid',
                values={"aid": anilist_id, "pid": pid}
            )
            for row in rows:
                await upstash_del(CacheKey.stream(row["episodeUrl"]))
            await database.execute(
                'DELETE FROM video_cache WHERE "episodeUrl" LIKE :url_pattern',
                values={"url_pattern": f"%{slug}%"}
            )

    result = await get_episode_stream(anilist_id, ep_float)

    if result is None:
        # Episode not in DB — maybe not synced yet
        has_eps = await ensure_episodes_exist(anilist_id)
        if has_eps:
            result = await get_episode_stream(anilist_id, ep_float)

    if not result or not result.get("sources"):
        raise HTTPException(
            status_code=503,
            detail=f"No video sources available for episode {ep_num}. "
                   "Sources may still be resolving — try again in a few seconds.",
        )

    return {"success": True, **result}


# ── POST /api/v2/anime/{anilist_id}/sync ───────────────────────────────────────

@router.post("/v2/anime/{anilist_id}/sync")
async def trigger_sync_v2(anilist_id: int, background_tasks: BackgroundTasks):
    """
    Manually trigger a full episode sync for an anime.
    Runs asynchronously — returns immediately.
    """
    background_tasks.add_task(sync_anime_episodes, anilist_id)
    return {
        "success": True,
        "message": f"Episode sync started for anilist_id={anilist_id}",
    }


@router.get("/v2/browse")
async def browse_anime(
    response: Response,
    page: int = Query(1, ge=1),
    sort: str = Query("score", pattern="^(score|popularity|trending|newest)$"),
    genre: str = Query(None),
    status: str = Query(None, pattern="^(RELEASING|FINISHED|NOT_YET_RELEASED)$"),
    limit: int = Query(24, le=50),
    q: str = Query(None, description="Search query"),
):
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    """Browse full anime catalog from database, with filter and sorting."""
    conditions = ['1=1']
    values = {"offset": (page - 1) * limit, "limit": limit}
    
    if q:
        conditions.append("meta.\"cleanTitle\" ILIKE :q OR meta.\"nativeTitle\" ILIKE :q")
        values["q"] = f"%{q}%"
    if genre:
        # Use simple ILIKE for JSONB array of strings or text representation
        conditions.append("meta.genres::text ILIKE :genre")
        values["genre"] = f"%{genre}%"
    if status:
        conditions.append('meta.status = :status')
        values["status"] = status
    
    sort_map = {
        "score": 'meta.score DESC NULLS LAST',
        "popularity": 'meta.popularity DESC NULLS LAST',
        "trending": 'meta.trending DESC NULLS LAST',
        "newest": 'meta."seasonYear" DESC NULLS LAST',
    }
    
    where_clause = " AND ".join(conditions)
    order_clause = sort_map.get(sort, 'meta.score DESC NULLS LAST')
    
    query = f"""
        SELECT meta.*, COUNT(e."episodeNumber") as episode_count
        FROM anime_metadata meta
        LEFT JOIN episodes e ON meta."anilistId" = e."anilistId"
        WHERE {where_clause}
        GROUP BY meta."anilistId"
        ORDER BY {order_clause}
        LIMIT :limit OFFSET :offset
    """
    
    try:
        rows = await database.fetch_all(query, values=values)
        return {"success": True, "page": page, "data": [dict(r) for r in rows]}
    except Exception as e:
        print(f"[Catalog] Browse error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── GET /api/v2/search ─────────────────────────────────────────────────────────

@router.get("/v2/search")
async def search_v2(
    response: Response,
    q: str = Query(..., min_length=2, description="Search query"),
    background_tasks: BackgroundTasks = None,
):
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
    """
    Search AniList and return results enriched with local DB status.

    Each result includes:
      - hasMapping: whether we already have provider mappings for it
      - providers: which providers we know about
      - hasEpisodes: whether the episode list is populated
    """
    cache_key = f"search_v2:{q.lower().strip()}"

    async def do_search():
        from services.anilist import fetch_anilist_info  # local import to avoid circulars
        result = await fetch_anilist_info(q)
        if not result:
            # Fallback to provider searches
            from services.pipeline import PROVIDERS
            tasks = []
            for name, provider in PROVIDERS.items():
                if hasattr(provider, 'search') and callable(getattr(provider, 'search')):
                    async def _safe_search(n, p, q):
                        try:
                            import asyncio
                            async with asyncio.timeout(10.0):
                                res = await p.search(q)
                                for item in res:
                                    item['source'] = n
                                return res
                        except Exception as e:
                            print(f"[{n}] Fallback search error: {e}")
                            return []
                    tasks.append(_safe_search(name, provider, q))
            
            if tasks:
                fallback_results = await asyncio.gather(*tasks)
                combined = []
                seen = set()
                for res_list in fallback_results:
                    for item in res_list:
                        title = item.get('title')
                        if title and title.lower() not in seen:
                            seen.add(title.lower())
                            # Format to match AniList structure as closely as possible
                            combined.append({
                                "anilistId": 0, # Fallback ID indicating no AniList link yet
                                "title": title,
                                "url": item.get('url'),
                                "source": item.get('source', 'unknown'),
                                "hasMapping": True, # Assume we can scrape it if we found it
                                "hasEpisodes": False,
                                "detailUrl": f"/anime/0?title={urllib.parse.quote_plus(title)}",
                            })
                if combined:
                    return combined
            return []

        anilist_id = result["anilistId"]
        mappings = await get_provider_mappings(anilist_id)

        count_row = await database.fetch_one(
            'SELECT COUNT(*) as cnt FROM episodes WHERE "anilistId" = :id',
            values={"id": anilist_id},
        )
        has_eps = count_row and count_row["cnt"] > 0

        # Save to DB in the background if new
        if not mappings and background_tasks:
            background_tasks.add_task(upsert_anime_db, result, "anilist_search", str(anilist_id))

        return [{
            **result,
            "hasMapping":  len(mappings) > 0,
            "providers":   list(mappings.keys()),
            "hasEpisodes": has_eps,
            # Canonical frontend route — always uses anilistId
            "detailUrl":   f"/anime/{anilist_id}",
        }]

    data = await swr_cache_get(cache_key, do_search, ttl=600, swr=3600)
    return {"success": True, "data": data or []}


# ── GET /api/v2/stats ──────────────────────────────────────────────────────────

@router.get("/v2/stats")
async def get_stats():
    """Return database statistics."""
    anime_count = await database.fetch_one('SELECT COUNT(*) as cnt FROM anime_metadata')
    episodes_count = await database.fetch_one('SELECT COUNT(*) as cnt FROM episodes')
    return {
        "success": True,
        "data": {
            "total_anime": anime_count["cnt"] if anime_count else 0,
            "total_episodes": episodes_count["cnt"] if episodes_count else 0
        }
    }

# ── POST /api/v2/sync-latest ───────────────────────────────────────────────────

@router.post("/v2/sync-latest")
async def sync_latest(background_tasks: BackgroundTasks):
    """
    Scrape latest from providers, map them, and sync episodes immediately via background tasks.
    Returns how many new mappings were found.
    """
    from services.background import scrape_oploverz_home, scrape_otakudesu_home, scrape_samehadaku_home, scrape_doronime_home
    from services.anilist import fetch_anilist_info
    from services.db import upsert_mapping_atomic
    
    results = await asyncio.gather(
        scrape_oploverz_home(),
        scrape_otakudesu_home(),
        scrape_samehadaku_home(),
        scrape_doronime_home(),
        return_exceptions=True
    )
    
    all_items = []
    for res in results:
        if isinstance(res, list):
            all_items.extend(res)

    seen_titles = set()
    items = []
    for item in all_items:
        t = item['title'].lower()
        if t not in seen_titles:
            seen_titles.add(t)
            items.append(item)

    processed_count = 0
    for item in items[:40]: # limit to 40 to avoid timeouts
        try:
            anilist_data = await fetch_anilist_info(item['title'])
            if anilist_data:
                await upsert_anime_db(anilist_data, "anilist_sync", str(anilist_data['anilistId']))
                await upsert_mapping_atomic(
                    anilist_id=anilist_data['anilistId'],
                    provider_id=item['provider_id'],
                    provider_slug=item['provider_slug'],
                    clean_title=anilist_data.get("cleanTitle") or anilist_data.get("nativeTitle", ""),
                    cover_image=anilist_data.get("hdImage") or anilist_data.get("coverImage", "")
                )
                # Use background_tasks to bypass QStash
                background_tasks.add_task(sync_anime_episodes, anilist_data['anilistId'])
                processed_count += 1
        except Exception as e:
            print(f"[SyncLatest] Error processing {item['title']}: {e}")

    return {
        "success": True,
        "message": f"Successfully mapped {processed_count} latest anime and started episode sync in background."
    }

# ── GET /api/v2/anime/{anilist_id}/mappings ────────────────────────────────────

@router.get("/v2/anime/{anilist_id}/mappings")
async def get_mappings_v2(anilist_id: int):
    """Debug endpoint: show all provider mappings for an anime."""
    mappings = await get_provider_mappings(anilist_id)
    return {"success": True, "anilistId": anilist_id, "mappings": mappings}


# ── internal helpers ───────────────────────────────────────────────────────────

async def _fetch_and_save_anilist(anilist_id: int) -> Optional[dict]:
    """
    Fetch a specific anime by its AniList ID (not by title).
    We query AniList with the numeric ID rather than doing a title search.
    """
    from services.clients import client

    QUERY = """
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        id
        title { romaji english native }
        coverImage { extraLarge large color }
        bannerImage
        averageScore popularity trending episodes status season seasonYear
        description(asHtml: false)
        genres
        studios { nodes { name isAnimationStudio } }
        recommendations { nodes { mediaRecommendation { id title { romaji english } coverImage { large } } } }
        nextAiringEpisode { episode timeUntilAiring }
      }
    }
    """
    try:
        resp = await client.post(
            "https://graphql.anilist.co",
            json={"query": QUERY, "variables": {"id": anilist_id}},
        )
        media = resp.json().get("data", {}).get("Media")
        if not media:
            return None

        studios = [s["name"] for s in media.get("studios", {}).get("nodes", []) if s.get("isAnimationStudio")]
        recs = [
            {
                "id": r["mediaRecommendation"]["id"],
                "title": r["mediaRecommendation"]["title"].get("english") or r["mediaRecommendation"]["title"].get("romaji"),
                "cover": r["mediaRecommendation"]["coverImage"]["large"],
            }
            for r in media.get("recommendations", {}).get("nodes", [])
            if r.get("mediaRecommendation")
        ]

        result = {
            "anilistId":        media["id"],
            "cleanTitle":       media["title"].get("english") or media["title"].get("romaji"),
            "nativeTitle":      media["title"].get("native"),
            "hdImage":          media["coverImage"].get("extraLarge") or media["coverImage"].get("large"),
            "color":            media["coverImage"].get("color"),
            "banner":           media.get("bannerImage"),
            "score":            media.get("averageScore"),
            "popularity":       media.get("popularity", 0),
            "trending":         media.get("trending", 0),
            "description":      media.get("description"),
            "genres":           media.get("genres", []),
            "totalEpisodes":    media.get("episodes"),
            "status":           media.get("status"),
            "season":           media.get("season"),
            "year":             media.get("seasonYear"),
            "studios":          studios,
            "recommendations":  recs,
            "nextAiringEpisode": media.get("nextAiringEpisode"),
        }

        # Save to DB
        await upsert_anime_db(result, "anilist_search", str(anilist_id))
        return result

    except Exception as e:
        print(f"[Catalog] _fetch_and_save_anilist error for {anilist_id}: {e}")
        return None
