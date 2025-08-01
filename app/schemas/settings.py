from pydantic import BaseModel, Field
from typing import List, Optional

class GlobalSettingsSchema(BaseModel):
    notification_url: Optional[str] = Field(
        default="",
        description=(
            "The notification service URL. Supports multiple services including:\n"
            "- Discord: discord://webhook_id/webhook_token\n"
            "- Telegram: tgram://bot_token/chat_id\n"
            "- Ntfy: ntfy://topic or ntfys://server/topic\n"
            "- Pushover: pover://user_key/app_token\n"
            "And many more. See Apprise documentation for all supported services."
        )
    )
    notifications_enabled: bool = True
    notify_online_global: bool = True
    notify_offline_global: bool = True
    notify_update_global: bool = True
    notify_favorite_category_global: bool = True
    http_proxy: Optional[str] = Field(
        default="",
        description="HTTP proxy URL for Streamlink (e.g., http://proxy.example.com:8080)"
    )
    https_proxy: Optional[str] = Field(
        default="",
        description="HTTPS proxy URL for Streamlink (e.g., https://proxy.example.com:8080)"
    )
    apprise_docs_url: str = "https://github.com/caronc/apprise/wiki"

    class Config:
        from_attributes = True

class StreamerNotificationSettingsSchema(BaseModel):
    streamer_id: int
    username: str | None = None
    profile_image_url: str | None = None
    notify_online: bool = True
    notify_offline: bool = True
    notify_update: bool = True
    notify_favorite_category: bool = True

    class Config:
        from_attributes = True
class StreamerNotificationSettingsUpdateSchema(BaseModel):
    """Schema für partielle Updates der Streamer-Benachrichtigungseinstellungen"""
    notify_online: Optional[bool] = None
    notify_offline: Optional[bool] = None
    notify_update: Optional[bool] = None
    notify_favorite_category: Optional[bool] = None
    
    class Config:
        from_attributes = True
