from pydantic import BaseModel
from typing import List, Optional

class SyncEpisodePayload(BaseModel):
    slug: str
    episode: float
    tg_urls: Optional[List[str]] = None
