from pydantic import BaseModel
from typing import Optional

class WatchProgressUpdate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
    progressSeconds: int
    durationSeconds: int
    isCompleted: bool

class WatchEventCreate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
    event_type: str # "start", "progress", "complete"
    timestamp_sec: int

class EpisodeLikeCreate(BaseModel):
    user_id: str
    anilistId: int
    episodeNumber: float
