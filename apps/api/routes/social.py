from fastapi import APIRouter, HTTPException
from typing import Optional
from db.connection import database
from db.models import episode_likes, activity_feed, follows, watch_history, anime_metadata, watch_sessions
from sqlalchemy import select, func, and_, desc, String
from sqlalchemy.dialects.postgresql import insert as pg_insert
from schemas.social import WatchProgressUpdate, WatchEventCreate, EpisodeLikeCreate, WatchSessionUpdate

router = APIRouter()

@router.post("/watch-session")
async def update_watch_session(item: WatchSessionUpdate):
    session_id = f"{item.user_id}_{item.anilist_id}_{item.episode_number}"
    is_completed = 1.0 if item.total_duration_sec > 0 and (item.watch_duration_sec / item.total_duration_sec) > 0.9 else (item.watch_duration_sec / item.total_duration_sec if item.total_duration_sec > 0 else 0.0)
    
    session_stmt = pg_insert(watch_sessions).values(
        session_id=session_id,
        user_id=item.user_id,
        anilist_id=item.anilist_id,
        episode_number=item.episode_number,
        watch_duration_sec=item.watch_duration_sec,
        total_duration_sec=item.total_duration_sec,
        drop_timestamp_sec=item.watch_duration_sec,
        completion_rate=is_completed,
        quality_watched=item.quality_watched,
        provider_used=item.provider_used,
        ended_at=func.now()
    ).on_conflict_do_update(
        index_elements=["session_id"],
        set_={
            "watch_duration_sec": func.greatest(watch_sessions.c.watch_duration_sec, item.watch_duration_sec),
            "total_duration_sec": item.total_duration_sec,
            "drop_timestamp_sec": item.watch_duration_sec,
            "completion_rate": func.greatest(watch_sessions.c.completion_rate, is_completed),
            "quality_watched": item.quality_watched,
            "provider_used": item.provider_used,
            "ended_at": func.now()
        }
    )
    await database.execute(session_stmt)
    return {"success": True}

@router.get("/progress")
async def get_watch_history(user_id: str):
    # Join with anime_metadata to get titles and images
    # We join on animeSlug = cast(anilistId as String)
    query = select(
        watch_history,
        anime_metadata.c.cleanTitle,
        anime_metadata.c.nativeTitle,
        anime_metadata.c.coverImage
    ).select_from(
        watch_history.outerjoin(anime_metadata, watch_history.c.animeSlug == func.cast(anime_metadata.c.anilistId, String))
    ).where(watch_history.c.userId == user_id).order_by(watch_history.c.updatedAt.desc())
    
    rows = await database.fetch_all(query=query)
    return [dict(row) for row in rows]

@router.post("/progress")
async def update_watch_history(item: WatchProgressUpdate):
    # Drizzle schema columns: userId, animeSlug, episode, timestampSec, durationSec, completed
    stmt = pg_insert(watch_history).values(
        userId=item.user_id,
        animeSlug=str(item.anilistId),
        episode=int(item.episodeNumber),
        timestampSec=item.progressSeconds,
        durationSec=item.durationSeconds,
        completed=item.isCompleted,
        updatedAt=func.now()
    ).on_conflict_do_update(
        index_elements=["userId", "animeSlug", "episode"],
        set_={
            "timestampSec": item.progressSeconds,
            "durationSec": item.durationSeconds,
            "completed": item.isCompleted,
            "updatedAt": func.now()
        }
    )
    await database.execute(stmt)
    
    return {"success": True}

@router.post("/watch-event")
async def record_watch_event(event: WatchEventCreate):
    # Upsert to Domain 2 structured tracking (watch_sessions)
    session_id = f"{event.user_id}_{event.anilistId}_{event.episodeNumber}"
    is_completed = 1.0 if event.event_type == "complete" else 0.0
    
    session_stmt = pg_insert(watch_sessions).values(
        session_id=session_id,
        user_id=event.user_id,
        anilist_id=event.anilistId,
        episode_number=event.episodeNumber,
        watch_duration_sec=event.timestamp_sec,
        drop_timestamp_sec=event.timestamp_sec,
        completion_rate=is_completed,
        ended_at=func.now()
    ).on_conflict_do_update(
        index_elements=["session_id"],
        set_={
            "watch_duration_sec": func.greatest(watch_sessions.c.watch_duration_sec, event.timestamp_sec),
            "drop_timestamp_sec": event.timestamp_sec,
            "completion_rate": func.greatest(watch_sessions.c.completion_rate, is_completed),
            "ended_at": func.now()
        }
    )
    await database.execute(session_stmt)
    
    # If completed, add to activity feed
    if event.event_type == "complete":
        feed_stmt = pg_insert(activity_feed).values(
            user_id=event.user_id,
            event_type="watched_episode",
            metadata={"anilistId": event.anilistId, "episodeNumber": event.episodeNumber}
        )
        await database.execute(feed_stmt)

    return {"success": True}

@router.get("/anime/{anilistId}/stats")
async def get_anime_stats(anilistId: int, user_id: Optional[str] = None):
    # Total watch count (unique watchers and total views) using watch_sessions
    watch_query = """
    SELECT COUNT(DISTINCT user_id) as total_watchers, 
           COUNT(DISTINCT session_id) as total_episode_views
    FROM watch_sessions
    WHERE "anilist_id" = :anilistId
    """
    stats = await database.fetch_one(query=watch_query, values={"anilistId": anilistId})
    
    return {
        "success": True,
        "total_watchers": stats["total_watchers"] if stats else 0,
        "total_episode_views": stats["total_episode_views"] if stats else 0,
    }

@router.get("/episode/{anilistId}/{episodeNumber}/stats")
async def get_episode_stats(anilistId: int, episodeNumber: float, user_id: Optional[str] = None):
    like_query = select(func.count(episode_likes.c.id)).where(
        and_(episode_likes.c.anilistId == anilistId, episode_likes.c.episodeNumber == episodeNumber)
    )
    likes_count = await database.fetch_val(like_query)
    
    user_liked = False
    if user_id:
        user_like_query = select(episode_likes).where(
            and_(
                episode_likes.c.user_id == user_id,
                episode_likes.c.anilistId == anilistId, 
                episode_likes.c.episodeNumber == episodeNumber
            )
        )
        user_liked = bool(await database.fetch_one(user_like_query))
        
    return {
        "success": True,
        "likes": likes_count or 0,
        "user_liked": user_liked
    }

@router.post("/episode/like")
async def toggle_episode_like(like: EpisodeLikeCreate):
    check_query = select(episode_likes).where(
        and_(
            episode_likes.c.user_id == like.user_id,
            episode_likes.c.anilistId == like.anilistId,
            episode_likes.c.episodeNumber == like.episodeNumber
        )
    )
    existing = await database.fetch_one(check_query)
    
    if existing:
        del_stmt = episode_likes.delete().where(episode_likes.c.id == existing.id)
        await database.execute(del_stmt)
        return {"success": True, "action": "removed"}
    else:
        ins_stmt = episode_likes.insert().values(
            user_id=like.user_id,
            anilistId=like.anilistId,
            episodeNumber=like.episodeNumber
        )
        await database.execute(ins_stmt)
        
        # Add to activity feed
        feed_stmt = pg_insert(activity_feed).values(
            user_id=like.user_id,
            event_type="liked_episode",
            metadata={"anilistId": like.anilistId, "episodeNumber": like.episodeNumber}
        )
        await database.execute(feed_stmt)
        
        return {"success": True, "action": "added"}

@router.get("/feed/{user_id}")
async def get_activity_feed(user_id: str):
    query = select(activity_feed).where(activity_feed.c.user_id == user_id).order_by(desc(activity_feed.c.created_at))
    rows = await database.fetch_all(query)
    return {"success": True, "feed": [dict(row) for row in rows]}

@router.get("/notifications")
async def get_global_notifications():
    # Fetch 20 most recently updated episodes that have tg-proxy
    from db.models import episodes
    query = select(
        episodes.c.anilistId,
        episodes.c.episodeNumber,
        episodes.c.updatedAt,
        anime_metadata.c.cleanTitle,
        anime_metadata.c.nativeTitle,
        anime_metadata.c.coverImage
    ).select_from(
        episodes.outerjoin(anime_metadata, episodes.c.anilistId == anime_metadata.c.anilistId)
    ).where(
        episodes.c.episodeUrl.like('%tg-proxy%') | episodes.c.episodeUrl.like('%workers.dev%')
    ).order_by(
        desc(episodes.c.updatedAt)
    ).limit(20)
    
    rows = await database.fetch_all(query)
    
    notifications = []
    import datetime
    
    def time_ago(dt):
        if not dt: return "Baru saja"
        now = datetime.datetime.utcnow()
        if dt.tzinfo:
            now = now.replace(tzinfo=datetime.timezone.utc)
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days} hari yang lalu"
        elif diff.seconds >= 3600:
            return f"{diff.seconds // 3600} jam yang lalu"
        elif diff.seconds >= 60:
            return f"{diff.seconds // 60} menit yang lalu"
        return "Baru saja"
        
    for i, r in enumerate(rows):
        title = r["cleanTitle"] or r["nativeTitle"] or f"Anime {r['anilistId']}"
        ep_num = r["episodeNumber"]
        notifications.append({
            "id": i + 1,
            "title": f"Episode Baru: {title}",
            "message": f"Episode {ep_num} sekarang tersedia dalam kualitas 1080p/720p! Tonton sekarang tanpa buffering.",
            "time": time_ago(r["updatedAt"]),
            "isUnread": True,
            "type": "new_episode",
            "link": f"/watch/{r['anilistId']}/{ep_num}"
        })
        
    return {"success": True, "data": notifications}

