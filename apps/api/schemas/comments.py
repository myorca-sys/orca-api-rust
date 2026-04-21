from pydantic import BaseModel
from typing import Optional

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
