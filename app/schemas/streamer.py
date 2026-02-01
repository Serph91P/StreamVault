from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class StreamerBase(BaseModel):
    username: str


class StreamerCreate(StreamerBase):
    pass


class Streamer(StreamerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: Optional[str] = None
    created_at: Optional[datetime] = None


class StreamerStatus(Streamer):
    is_live: bool
    last_updated: Optional[datetime] = None
    title: Optional[str] = None
    category: Optional[str] = None
