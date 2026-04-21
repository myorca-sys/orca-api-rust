from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from db.connection import database
from db.models import collections, users as user_table, anime_metadata
from sqlalchemy import select, delete, func, String
from sqlalchemy.dialects.postgresql import insert as pg_insert
from schemas.collection import CollectionUpdate

router = APIRouter()

@router.get("")
async def get_collection(user_id: str):
    query = select(
        collections,
        anime_metadata.c.coverImage,
        anime_metadata.c.cleanTitle,
        anime_metadata.c.nativeTitle,
        anime_metadata.c.totalEpisodes
    ).select_from(
        collections.outerjoin(anime_metadata, collections.c.animeSlug == func.cast(anime_metadata.c.anilistId, String))
    ).where(collections.c.userId == user_id).order_by(collections.c.updatedAt.desc())
    
    rows = await database.fetch_all(query=query)
    return [dict(row) for row in rows]

@router.post("")
async def save_collection(coll: CollectionUpdate):
    stmt = pg_insert(collections).values(
        userId=coll.user_id,
        animeSlug=coll.anilistId,
        status=coll.status,
        progress=coll.progress
    ).on_conflict_do_update(
        index_elements=["userId", "animeSlug"],
        set_={"status": coll.status, "progress": coll.progress, "updatedAt": func.now()}
    )
    await database.execute(stmt)
    return {"success": True}

@router.delete("")
async def remove_collection(user_id: str, anilistId: str):
    stmt = delete(collections).where((collections.c.userId == user_id) & (collections.c.animeSlug == anilistId))
    await database.execute(stmt)
    return {"success": True}
