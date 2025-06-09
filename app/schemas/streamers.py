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
    original_profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class StreamerList(BaseModel):
    streamers: List[StreamerResponse]

# New schemas for streamer settings
class StreamerCustomNotificationSettingsSchema(BaseModel):
    notify_online: Optional[bool] = None
    notify_offline: Optional[bool] = None
    notify_title_change: Optional[bool] = None
    notify_game_change: Optional[bool] = None
    notify_new_vod: Optional[bool] = None

class StreamerCustomRecordingSettingsSchema(BaseModel):
    enabled: Optional[bool] = None
    quality: Optional[str] = None
    custom_filename: Optional[str] = None
    max_streams: Optional[int] = None

class AddStreamerSettingsSchema(BaseModel):
    notifications: Optional[StreamerCustomNotificationSettingsSchema] = None
    recording: Optional[StreamerCustomRecordingSettingsSchema] = None
