"""
Route: /api/v2/stream  (Resilient Edition)
==========================================
Arsitektur utama — Resilient Mapping Resolution:

  ┌──────────────────────────────────────────────────────────────┐
  │                   MAPPING RESOLUTION LADDER                  │
  │                                                              │
  │  Tier 1 ─ reconciler.reconcile()  (DB + hint)    max 12s    │
  │       │  mappings found? ──YES──► proceed to scrape          │
  │       │  NO / partial                                        │
  │       ▼                                                      │
  │  Tier 2 ─ on-the-fly reconcile with title variants  max 8s  │
  │       │  kebab-slug, cleaned title, native title             │
  │       │  any new mapping found? ──YES──► merge & proceed     │
  │       │  STILL missing providers?                            │
  │       ▼                                                      │
  │  Tier 3 ─ last-resort direct search per provider    max 6s  │
  │           search HTML → extract seriesUrl inline            │
  │           (skips reconciler entirely for that provider)      │
  └──────────────────────────────────────────────────────────────┘
"""
import asyncio
import time
import urllib.parse
import re
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
import httpx

from utils.ssrf_guard import validate_scrape_url, SSRFError
from utils.helpers import extract_domain, determine_quality
from services.config import HEADERS
from services.providers import oploverz_provider, otakudesu_provider, samehadaku_provider, kuronime_provider, extractor
from services.reconciler import reconciler
from services.anilist import fetch_anilist_info_by_id
from db.connection import database

router = APIRouter()

# ---------------------------------------------------------------------------
# Provider Scrape Helpers
# ---------------------------------------------------------------------------
PROVIDER_TIMEOUT = 10.0
EXTRACTOR_TIMEOUT = 7.0
# Prioritize 720p for ingestion (Zero-cost optimization), fallback to 1080p if 720p missing
QUALITY_RANK = {"720p": 5, "1080p": 4, "480p": 3, "360p": 2, "Auto": 1}

async def _resolve_embed(embed: dict, source_tag: str) -> Optional[dict]:
    url = embed.get('url') or embed.get('resolved', '')
    if not url: return None
    try:
        if embed.get('type') == 'direct':
            resolved = url
        else:
            async with asyncio.timeout(EXTRACTOR_TIMEOUT):
                resolved = await extractor.extract_raw_video(url)
            
        is_direct = embed.get('type') == 'direct' or resolved.endswith(('.m3u8', '.mp4')) or 'videoplayback' in resolved or 'workers.dev' in resolved or 'tg-proxy' in resolved
        quality = determine_quality(embed.get('quality', 'Auto'))
        
        # Wrap mp4upload or other direct links with our CF proxy to bypass CORS / Referer restrictions
        if is_direct and 'workers.dev' not in resolved and 'tg-proxy' not in resolved:
            # Let's import sign_stream_url
            try:
                from utils.signed_url import sign_stream_url
                # Identify proxy provider tag based on the URL or source tag
                provider_for_proxy = "mp4upload" if "mp4upload" in url else source_tag
                resolved = sign_stream_url(resolved, provider_for_proxy, quality)
            except Exception as e:
                print(f"Error wrapping signed url: {e}")

        return {
            'provider':  embed.get('provider', source_tag),
            'domain':    extract_domain(resolved),
            'quality':   quality,
            'url':       resolved,
            'embed_url': url,
            'type':      'direct' if is_direct else 'iframe',
            'source':    source_tag,
        }
    except: return None

async def _scrape_samehadaku(title: str, episode_num: float, series_url: str = None, target_anilist_id: int = None) -> Dict[str, Any]:
    try:
        async with asyncio.timeout(PROVIDER_TIMEOUT):
            if series_url:
                details = await samehadaku_provider.get_anime_detail(series_url)
            else:
                results = await samehadaku_provider.search(title)
                if not results: return {'sources': [], 'provider': 'samehadaku'}
                
                # If we have target_anilist_id, try to find the exact match
                if target_anilist_id:
                    series_url = None
                    for res in results[:3]: # Check top 3 results
                        slug = res['url'].strip('/').split('/')[-1]
                        recon = await reconciler.reconcile("samehadaku", slug, res['title'])
                        if recon and recon.canonical_anilist_id == target_anilist_id:
                            series_url = res['url']
                            break
                    if not series_url: return {'sources': [], 'provider': 'samehadaku'}
                else:
                    series_url = results[0]['url']
                    
                details = await samehadaku_provider.get_anime_detail(series_url)
                
            if not details: return {'sources': [], 'provider': 'samehadaku'}
            target_url = next(
                (e['url'] for e in details.get('episodes', [])
                 if re.search(fr'\b{episode_num}\b', e['title'])), None
            )
            if not target_url: return {'sources': [], 'provider': 'samehadaku'}
            raw = await samehadaku_provider.get_episode_sources(target_url)
            embeds = raw if isinstance(raw, list) else raw.get('sources', [])
            resolved = await asyncio.gather(*[_resolve_embed(e, 'samehadaku') for e in embeds])
            return {'sources': [s for s in resolved if s], 'provider': 'samehadaku'}
    except:
        return {'sources': [], 'provider': 'samehadaku'}

async def _scrape_oploverz(episode_url: str) -> Dict[str, Any]:
    try:
        async with asyncio.timeout(PROVIDER_TIMEOUT):
            res = await oploverz_provider.get_episode_sources(episode_url)
        
        embeds = res if isinstance(res, list) else res.get('sources', [])
        resolved = await asyncio.gather(*[_resolve_embed(e, 'oploverz') for e in embeds])
        
        downloads = res.get('downloads', []) if isinstance(res, dict) else []
        
        return {'sources': [s for s in resolved if s], 'downloads': downloads, 'provider': 'oploverz'}
    except Exception as e:
        print(f"[Oploverz] Error: {e}")
        return {'sources': [], 'downloads': [], 'provider': 'oploverz'}

async def _scrape_otakudesu(series_url: str, episode_num: float) -> Dict[str, Any]:
    try:
        async with asyncio.timeout(PROVIDER_TIMEOUT):
            details = await otakudesu_provider.get_anime_detail(series_url)
        if not details: return {'sources': [], 'provider': 'otakudesu'}
        
        target_url = next(
            (e['url'] for e in details.get('episodes', []) 
             if re.search(fr'\b{int(episode_num)}\b', e['title'])), 
            None
        )
        if not target_url: return {'sources': [], 'provider': 'otakudesu'}
        
        raw = await otakudesu_provider.get_episode_sources(target_url)
        embeds = raw if isinstance(raw, list) else raw.get('sources', [])
        
        # Filter hanya yang punya URL valid
        valid = [e for e in embeds if e.get('url') and e['url'].startswith('http')]
        
        resolved = await asyncio.gather(*[_resolve_embed(e, 'otakudesu') for e in valid])
        return {'sources': [s for s in resolved if s], 'provider': 'otakudesu'}
    except Exception as e:
        print(f"[Otakudesu] Error: {e}")
        return {'sources': [], 'provider': 'otakudesu'}

async def _scrape_kuronime(title: str, episode_num: float, series_url: str = None, target_anilist_id: int = None) -> Dict[str, Any]:
    try:
        async with asyncio.timeout(PROVIDER_TIMEOUT):
            if series_url:
                details = await kuronime_provider.get_anime_detail(series_url)
            else:
                results = await kuronime_provider.search(title)
                if not results: return {'sources': [], 'provider': 'kuronime'}
                
                if target_anilist_id:
                    series_url = None
                    for res in results[:3]:
                        slug = res['url'].strip('/').split('/')[-1]
                        recon = await reconciler.reconcile("kuronime", slug, res['title'])
                        if recon and recon.canonical_anilist_id == target_anilist_id:
                            series_url = res['url']
                            break
                    if not series_url: return {'sources': [], 'provider': 'kuronime'}
                else:
                    series_url = results[0]['url']
                    
                details = await kuronime_provider.get_anime_detail(series_url)
                
            if not details: return {'sources': [], 'provider': 'kuronime'}
            target_url = next((e['url'] for e in details.get('episodes', []) if re.search(fr'\b{episode_num}\b', e['title'])), None)
            if not target_url: return {'sources': [], 'provider': 'kuronime'}
            raw = await kuronime_provider.get_episode_sources(target_url)
            embeds = raw if isinstance(raw, list) else raw.get('sources', [])
            resolved = await asyncio.gather(*[_resolve_embed(e, 'kuronime') for e in embeds])
            return {'sources': [s for s in resolved if s], 'provider': 'kuronime'}
    except:
        return {'sources': [], 'provider': 'kuronime'}

# ---------------------------------------------------------------------------
# Tier-3 Last Resort Helpers
# ---------------------------------------------------------------------------
async def _last_resort_otakudesu(title: str, episode_num: float) -> Dict[str, Any]:
    try:
        async with asyncio.timeout(8.0):
            q = urllib.parse.quote_plus(title)
            r = await otakudesu_provider.client.get(f"https://otakudesu.blog/?s={q}&post_type=anime")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'lxml')
            first = soup.select_one('ul.chivsrc li h2 a')
            if not first:
                first = soup.select_one('ul.chbox li h2 a')
            if not first:
                first = soup.select_one('ul.chbox li a')
            if not first: return {'sources': [], 'provider': 'otakudesu', 'tier': 3}
            return await _scrape_otakudesu(first.get('href'), episode_num)
    except: return {'sources': [], 'provider': 'otakudesu', 'tier': 3}

# ---------------------------------------------------------------------------
# Core Logic
# ---------------------------------------------------------------------------
def _title_variants(title: str, anilist_info: dict = None) -> list[str]:
    variants = [title.strip()]
    cleaned = re.sub(r'\b(sub\s*indo|batch|bd|ova|season\s*\d+)\b', '', title, flags=re.IGNORECASE).strip()
    if cleaned not in variants: variants.append(cleaned)
    
    if anilist_info:
        if anilist_info.get('romajiTitle') and anilist_info['romajiTitle'] not in variants:
            variants.append(anilist_info['romajiTitle'])
        if anilist_info.get('cleanTitle') and anilist_info['cleanTitle'] not in variants:
            variants.append(anilist_info['cleanTitle'])
            
        if anilist_info.get('synonyms'):
            for syn in anilist_info['synonyms']:
                # Allow typical romaji/english aliases, ignore super short or weird ones
                if re.match(r'^[a-zA-Z0-9\s\-_:\.!]+$', syn) and len(syn) > 2:
                    if syn not in variants:
                        variants.append(syn)
                        
    return [v for v in variants if v][:6]

@router.get('/stream/sources')
async def get_sources_v2(
    title: str = Query(..., description="Anime title"),
    ep: int = Query(..., description="Episode number"),
    anilist_id: int = Query(None, description="Anilist ID")
):
    start_ts = time.monotonic()
    
    anilist_info = None
    if anilist_id:
        try:
            anilist_info = await fetch_anilist_info_by_id(anilist_id)
        except Exception as e:
            print(f"[StreamV2] Error fetching anilist info: {e}")

    # Tier 0: Check DB for existing tg-proxy stream (0ms latensi)
    if anilist_id:
        try:
            row = await database.fetch_one(
                """
                SELECT id, "episodeUrl", "providerId"
                FROM   episodes
                WHERE  "anilistId" = :anilist_id AND "episodeNumber" = :ep_num
                AND ("episodeUrl" LIKE '%tg-proxy%' OR "episodeUrl" LIKE '%workers.dev%')
                LIMIT 1
                """,
                values={"anilist_id": anilist_id, "ep_num": float(ep)}
            )
            if row:
                ep_url = row["episodeUrl"]
                return {
                    'success': True,
                    'sources': [{
                        'provider': 'Swarm Storage (Telegram)',
                        'quality': '1080p',
                        'url': ep_url,
                        'type': 'hls' if ep_url.endswith('.m3u8') or 'tg-proxy' in ep_url else 'mp4',
                        'source': 'telegram_swarm'
                    }],
                    'elapsed_ms': int((time.monotonic() - start_ts) * 1000)
                }
        except Exception as e:
            print(f"[StreamV2] Tier 0 error: {e}")

    # Tier 1 & 2: Get Mappings from DB
    mappings = {}
    if anilist_id:
        try:
            rows = await database.fetch_all(
                'SELECT "providerId", "providerSlug" FROM anime_mappings WHERE "anilistId" = :aid',
                values={"aid": anilist_id}
            )
            for r in rows:
                mappings[r["providerId"]] = r["providerSlug"]
        except Exception as e:
            print(f"[StreamV2] Mapping DB error: {e}")

    title_vars = _title_variants(title, anilist_info)
    
    if not mappings:
        for variant in title_vars:
            try:
                async with asyncio.timeout(10.0):
                    recon_result = await reconciler.reconcile(provider_id="stream_query", provider_slug="none", raw_title=variant)
                    if recon_result and recon_result.anilist_metadata:
                        # Fallback to query DB again with the found Anilist ID
                        found_id = recon_result.canonical_anilist_id
                        rows = await database.fetch_all(
                            'SELECT "providerId", "providerSlug" FROM anime_mappings WHERE "anilistId" = :aid',
                            values={"aid": found_id}
                        )
                        for r in rows:
                            mappings[r["providerId"]] = r["providerSlug"]
                        if mappings: break
            except: continue

    scrape_tasks = []
    providers_attempted = []

    # Focus on all providers that can yield Direct Streams (Wibufile, DesuDrives, 4meplayer)
    
    # 1. Samehadaku (Wibufile, etc)
    from services.pipeline import build_provider_series_url
    if mappings and 'samehadaku' in mappings:
        series_url = build_provider_series_url('samehadaku', mappings['samehadaku'])
        scrape_tasks.append(_scrape_samehadaku(title_vars[0], ep, series_url, target_anilist_id=anilist_id))
    else:
        async def fallback_samehadaku_search():
            for v in title_vars:
                res = await _scrape_samehadaku(v, ep, target_anilist_id=anilist_id)
                if res and res.get('sources'): return res
            return {'sources': [], 'provider': 'samehadaku'}
        scrape_tasks.append(fallback_samehadaku_search())
    providers_attempted.append('samehadaku')
    
    # 2. Oploverz (4meplayer, Oplo2, Blogger)
    # Oploverz often uses title-based slugs, so we can try slugifying variants
    async def fallback_oploverz_search():
        if mappings and 'oploverz' in mappings:
            slug = mappings['oploverz']
            res = await _scrape_oploverz(f"https://o.oploverz.ltd/series/{slug}/episode/{ep}/")
            if res and res.get('sources'): return res
            
        for v in title_vars:
            slug = v.lower().replace(' ', '-')
            res = await _scrape_oploverz(f"https://o.oploverz.ltd/series/{slug}/episode/{ep}/")
            if res and res.get('sources'):
                return res
        return {'sources': [], 'downloads': [], 'provider': 'oploverz'}
        
    scrape_tasks.append(fallback_oploverz_search())
    providers_attempted.append('oploverz')

    # 3. Otakudesu (DesuDrives, Blogger)
    if mappings and 'otakudesu' in mappings:
        scrape_tasks.append(_scrape_otakudesu(f"https://otakudesu.blog/anime/{mappings['otakudesu']}/", ep))
    else:
        # Fallback to search, try variants if the main title fails
        async def fallback_otakudesu_search():
            for v in title_vars:
                res = await _last_resort_otakudesu(v, ep)
                if res and res.get('sources'):
                    return res
            return {'sources': [], 'provider': 'otakudesu', 'tier': 3}
            
        scrape_tasks.append(fallback_otakudesu_search())
    providers_attempted.append('otakudesu')
    
    # 4. Kuronime (KuroPlayer, HLS, Kraken)
    if mappings and 'kuronime' in mappings:
        series_url = build_provider_series_url('kuronime', mappings['kuronime'])
        scrape_tasks.append(_scrape_kuronime(title_vars[0], ep, series_url, target_anilist_id=anilist_id))
    else:
        async def fallback_kuronime_search():
            for v in title_vars:
                res = await _scrape_kuronime(v, ep, target_anilist_id=anilist_id)
                if res and res.get('sources'):
                    return res
            return {'sources': [], 'provider': 'kuronime'}
        scrape_tasks.append(fallback_kuronime_search())
    providers_attempted.append('kuronime')

    if not scrape_tasks:
        raise HTTPException(status_code=503, detail="All providers down or mapping failed.")

    results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
    
    all_sources = []
    for res in results:
        if isinstance(res, dict) and res.get('sources'):
            all_sources.extend(res['sources'])

    # FILTER: ONLY DIRECT LINKS
    all_sources = [s for s in all_sources if s.get('type') == 'direct']

    all_sources.sort(key=lambda x: QUALITY_RANK.get(x.get('quality', 'Auto'), 1), reverse=True)

    # Ingestion Trigger: Jika ditemukan direct link, masukkan ke antrean Telegram Swarm
    if all_sources and anilist_id:
        best = all_sources[0]
        raw_url = best.get('url', '')
        if raw_url and 'workers.dev' not in raw_url and 'tg-proxy' not in raw_url:
            try:
                # Dapatkan episode_id dari database untuk update URL nantinya
                row = await database.fetch_one(
                    'SELECT id FROM episodes WHERE "anilistId" = :aid AND "episodeNumber" = :ep LIMIT 1',
                    values={"aid": anilist_id, "ep": float(ep)}
                )
                if row:
                    from services.queue import enqueue_ingest_batch
                    asyncio.create_task(enqueue_ingest_batch())
            except Exception as e:
                print(f"[StreamV2] Ingestion Trigger Error: {e}")

    return {
        'success': len(all_sources) > 0,
        'sources': all_sources,
        'elapsed_ms': int((time.monotonic() - start_ts) * 1000)
    }
