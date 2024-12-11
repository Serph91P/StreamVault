from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StreamerBase(BaseModel):
    username: str

class StreamerCreate(StreamerBase):
    pass

class Streamer(StreamerBase):
    id: int
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class StreamerStatus(Streamer):
    is_live: bool
    last_updated: Optional[datetime] = None
    title: Optional[str] = None
    category: Optional[str] = None
