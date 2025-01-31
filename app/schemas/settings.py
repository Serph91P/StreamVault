from pydantic import BaseModel

class NotificationSettingsSchema(BaseModel):
    notification_url: str | None = None
    notifications_enabled: bool = True

    class Config:
        from_attributes = True
