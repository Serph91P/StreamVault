from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class StreamerBase(BaseModel):
    username: str


class StreamerCreate(StreamerBase):
    settings: Optional[Dict[str, Any]] = None


class StreamerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    # Last stream information (shown when offline)
    last_stream_title: Optional[str] = None
    last_stream_category_name: Optional[str] = None
    last_stream_viewer_count: Optional[int] = None
    last_stream_ended_at: Optional[datetime] = None


class StreamerList(BaseModel):
    streamers: List[StreamerResponse]
