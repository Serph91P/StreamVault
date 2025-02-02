from pydantic import BaseModel

class GlobalSettingsSchema(BaseModel):
    notification_url: str | None = None
    notifications_enabled: bool = True

    class Config:
        from_attributes = True

class StreamerNotificationSettingsSchema(BaseModel):
    id: int | None = None
    streamer_id: int
    notify_online: bool = True
    notify_offline: bool = True 
    notify_update: bool = True

    class Config:
        from_attributes = True