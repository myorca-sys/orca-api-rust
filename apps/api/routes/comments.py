from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from db.connection import database
from db.models import comments, comment_reactions
from sqlalchemy import select, func, and_, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert

router = APIRouter()

class CommentCreate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
    text: str
    parent_id: Optional[int] = None
    is_spoiler: bool = False
    timestamp_sec: Optional[int] = None

class CommentReaction(BaseModel):
    user_id: str
    comment_id: int
    emoji: str # e.g., "like", "love", "laugh"

@router.get("/")
async def get_comments(anilistId: int, episodeNumber: float, user_id: Optional[str] = None):
    # Fetch comments for an episode
    query = """
    SELECT 
        c.id, c.user_id, u.name as username, u.image as avatar, 
        c.text, c.timestamp_sec, c.created_at, c.parent_id,
        COUNT(cr.id) FILTER (WHERE cr.emoji = 'like') as likes_count,
        EXISTS(SELECT 1 FROM comment_reactions WHERE comment_id = c.id AND user_id = :user_id AND emoji = 'like') as user_liked
    FROM comments c
    LEFT JOIN "user" u ON c.user_id = u.id
    LEFT JOIN comment_reactions cr ON c.id = cr.comment_id
    WHERE c."anilistId" = :anilistId AND c."episodeNumber" = :episodeNumber
    GROUP BY c.id, u.name, u.image
    ORDER BY c.created_at DESC
    """
    rows = await database.fetch_all(query=query, values={"anilistId": anilistId, "episodeNumber": episodeNumber, "user_id": user_id or ""})
    
    # Organize into a tree (parents and replies)
    comment_map = {}
    top_level = []
    
    for row in rows:
        c = dict(row)
        c["replies"] = []
        comment_map[c["id"]] = c
        
    for c in comment_map.values():
        if c["parent_id"] and c["parent_id"] in comment_map:
            comment_map[c["parent_id"]]["replies"].append(c)
        else:
            top_level.append(c)
            
    return top_level

@router.post("")
async def post_comment(comment: CommentCreate):
    stmt = pg_insert(comments).values(
        user_id=comment.user_id,
        anilistId=comment.anilistId,
        episodeNumber=comment.episodeNumber,
        text=comment.text,
        parent_id=comment.parent_id,
        timestamp_sec=comment.timestamp_sec
    ).returning(comments.c.id)
    
    try:
        new_id = await database.execute(stmt)
        return {"success": True, "id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reaction")
async def toggle_reaction(reaction: CommentReaction):
    # Check if exists
    check_query = select(comment_reactions).where(
        and_(
            comment_reactions.c.comment_id == reaction.comment_id,
            comment_reactions.c.user_id == reaction.user_id,
            comment_reactions.c.emoji == reaction.emoji
        )
    )
    existing = await database.fetch_one(check_query)
    
    if existing:
        # Remove reaction (unlike)
        del_stmt = comment_reactions.delete().where(comment_reactions.c.id == existing.id)
        await database.execute(del_stmt)
        return {"success": True, "action": "removed"}
    else:
        # Add reaction (like)
        ins_stmt = comment_reactions.insert().values(
            comment_id=reaction.comment_id,
            user_id=reaction.user_id,
            emoji=reaction.emoji
        )
        await database.execute(ins_stmt)
        return {"success": True, "action": "added"}
