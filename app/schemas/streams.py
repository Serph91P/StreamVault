from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StreamBase(BaseModel):
    streamer_id: int
    title: Optional[str] = None
    category_name: Optional[str] = None
    language: Optional[str] = None
    
class StreamResponse(StreamBase):
    id: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    twitch_stream_id: Optional[str] = None
    is_live: bool = False
    
    class Config:
        from_attributes = True

class StreamList(BaseModel):
    streams: List[StreamResponse]