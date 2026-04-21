from pydantic import BaseModel

class CollectionUpdate(BaseModel):
    user_id: str
    anilistId: str
    status: str
    progress: float = 0
