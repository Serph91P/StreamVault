from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class StreamerBase(BaseModel):
    username: str
    
class StreamerCreate(StreamerBase):
    settings: Optional[Dict[str, Any]] = None

class StreamerResponse(BaseModel):
    id: int
    twitch_id: str
    username: str
    is_live: bool
    is_recording: bool = False  # Whether currently recording
    recording_enabled: bool = True  # Whether recording is enabled for this streamer (default True)
    active_stream_id: Optional[int] = None
    title: Optional[str] = None
    category_name: Optional[str] = None
    language: Optional[str] = None
    last_updated: Optional[datetime] = None
    profile_image_url: Optional[str] = None
    original_profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class StreamerList(BaseModel):
    streamers: List[StreamerResponse]
