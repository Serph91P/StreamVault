from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class StreamerBase(BaseModel):
    username: str
    
class StreamerCreate(StreamerBase):
    pass

class StreamerResponse(BaseModel):
    id: int
    twitch_id: str
    username: str
    is_live: bool
    title: Optional[str] = None
    category_name: Optional[str] = None
    language: Optional[str] = None
    last_updated: Optional[datetime] = None
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class StreamerList(BaseModel):
    streamers: List[StreamerResponse]
