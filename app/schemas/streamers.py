from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class StreamerBase(BaseModel):
    username: str
    
class StreamerCreate(StreamerBase):
    pass

class StreamerResponse(StreamerBase):
    id: int
    twitch_id: str
    display_name: str
    is_live: bool
    title: Optional[str] = None
    category_name: Optional[str] = None
    language: Optional[str] = None
    last_updated: Optional[datetime] = None

    class Config:
        from_attributes = True

class StreamerList(BaseModel):
    streamers: List[StreamerResponse]
