from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StreamerBase(BaseModel):
    username: str

class StreamerCreate(StreamerBase):
    pass

class Streamer(StreamerBase):
    id: int
    
    class Config:
        from_attributes = True

class StreamerStatus(Streamer):
    is_live: bool
    last_updated: Optional[datetime] = None
