from fastapi import APIRouter, Response
from db.connection import database
import json

router = APIRouter()

@router.get("/v2/home")
async def get_home_v2(response: Response):
    response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=120"
    """
    Return homepage data exclusively from our database (datacenter).
    Ensures we only show anime that actually exist in our DB and have episodes.
    """
    # Run queries concurrently to save round-trips
    import asyncio
    
    hero_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."synopsis", m."score", m."nextAiringEpisode",
               COALESCE((SELECT MAX(raw_value::numeric) FROM metadata_sources ms WHERE ms.canonical_id = c.id AND ms.field_name = 'views_local'), 0) + COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId" AND date >= CURRENT_DATE - INTERVAL '7 days'), 0) as local_trending
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_trending DESC, m.trending DESC NULLS LAST, m.popularity DESC NULLS LAST, m.score DESC NULLS LAST
        LIMIT 10
    '''
    
    airing_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score", m."nextAiringEpisode",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE m.status = 'RELEASING' AND EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST
        LIMIT 20
    '''
    
    latest_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               max(e."episodeNumber") as "latestEpisode",
               max(e."updatedAt") as last_up
        FROM anime_metadata m
        JOIN episodes e ON m."anilistId" = e."anilistId"
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE m.status != 'FINISHED' OR m.status IS NULL
        GROUP BY m."anilistId", c.title_preferred, m."cleanTitle", m."nativeTitle", m."coverImage", m."bannerImage", m."score"
        ORDER BY last_up DESC
        LIMIT 20
    '''
    
    popular_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST, m.score DESC NULLS LAST
        LIMIT 20
    '''

    completed_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score", 
               COALESCE(c.episode_count_actual, m."totalEpisodes") as "totalEpisodes",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE m.status = 'FINISHED' AND EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST, m.score DESC NULLS LAST
        LIMIT 20
    '''

    top_rated_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY m.score DESC NULLS LAST, local_views DESC, m.popularity DESC NULLS LAST
        LIMIT 20
    '''

    isekai_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE (m.genres::text ILIKE '%fantasy%' OR c.genres_local::text ILIKE '%fantasy%' OR c.genres_local::text ILIKE '%isekai%') 
          AND EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST
        LIMIT 20
    '''

    movies_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId"), 0) as local_views
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE (m."totalEpisodes" = 1 OR c.episode_count_actual = 1) AND EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_views DESC, m.popularity DESC NULLS LAST
        LIMIT 20
    '''

    trending_query = '''
        SELECT m."anilistId", 
               COALESCE(c.title_preferred, m."cleanTitle") as "cleanTitle", 
               m."nativeTitle", m."coverImage", m."bannerImage", m."score",
               COALESCE((SELECT MAX(raw_value::numeric) FROM metadata_sources ms WHERE ms.canonical_id = c.id AND ms.field_name = 'views_local'), 0) + COALESCE((SELECT SUM(views) FROM daily_anime_stats d WHERE d."anilistId" = m."anilistId" AND date >= CURRENT_DATE - INTERVAL '7 days'), 0) as local_trending
        FROM anime_metadata m
        LEFT JOIN canonical_anime c ON m."anilistId" = c.anilist_id
        WHERE EXISTS (SELECT 1 FROM episodes e WHERE e."anilistId" = m."anilistId")
        ORDER BY local_trending DESC, m.trending DESC NULLS LAST, m.popularity DESC NULLS LAST
        LIMIT 20
    '''

    hero_rows, airing_rows, latest_rows, popular_rows, completed_rows, top_rated_rows, isekai_rows, movies_rows, trending_rows = await asyncio.gather(
        database.fetch_all(hero_query),
        database.fetch_all(airing_query),
        database.fetch_all(latest_query),
        database.fetch_all(popular_query),
        database.fetch_all(completed_query),
        database.fetch_all(top_rated_query),
        database.fetch_all(isekai_query),
        database.fetch_all(movies_query),
        database.fetch_all(trending_query)
    )

    def format_anime(r):
        d = dict(r)
        if "nextAiringEpisode" in d and isinstance(d["nextAiringEpisode"], str):
            try:
                d["nextAiringEpisode"] = json.loads(d["nextAiringEpisode"])
            except Exception:
                pass
        return {
            "id": str(d["anilistId"]),
            "title": d.get("cleanTitle") or d.get("nativeTitle"),
            "img": d.get("coverImage"),
            "banner": d.get("bannerImage"),
            "score": d.get("score"),
            "synopsis": d.get("synopsis"),
            "nextAiringEpisode": d.get("nextAiringEpisode"),
            "url": f"/anime/{d['anilistId']}",
            "anilistId": d["anilistId"],
            "latestEpisode": d.get("latestEpisode"),
            "episodes": d.get("totalEpisodes")
        }

    return {
        "success": True,
        "data": {
            "hero": [format_anime(r) for r in hero_rows],
            "airing": [format_anime(r) for r in airing_rows],
            "latest": [format_anime(r) for r in latest_rows],
            "popular": [format_anime(r) for r in popular_rows],
            "completed": [format_anime(r) for r in completed_rows],
            "top_rated": [format_anime(r) for r in top_rated_rows],
            "isekai": [format_anime(r) for r in isekai_rows],
            "movies": [format_anime(r) for r in movies_rows],
            "trending": [format_anime(r) for r in trending_rows],
        }
    }