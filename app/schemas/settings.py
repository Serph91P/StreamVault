from pydantic import BaseModel, HttpUrl
from typing import Optional

class GlobalSettingsSchema(BaseModel):
    notification_url: Optional[str] = None
    notifications_enabled: bool = True
    apprise_docs_url: str = "https://github.com/caronc/apprise/wiki"

    class Config:
        from_attributes = True

class StreamerNotificationSettingsSchema(BaseModel):
    id: Optional[int] = None
    streamer_id: int
    notify_online: bool = True
    notify_offline: bool = True 
    notify_update: bool = True

    class Config:
        from_attributes = True