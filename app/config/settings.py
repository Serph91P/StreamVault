from pydantic_settings import BaseSettings
from typing import Optional
import secrets
from typing import List

class Settings(BaseSettings):
    TWITCH_APP_ID: str
    TWITCH_APP_SECRET: str
    BASE_URL: str
    WEBHOOK_URL: Optional[str] = None
    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    EVENTSUB_PORT: int = 8080
    EVENTSUB_SECRET: str = secrets.token_urlsafe(32)
    APPRISE_URLS: List[str] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.WEBHOOK_URL:
            base = self.BASE_URL.rstrip('/')
            self.WEBHOOK_URL = base

    class Config:
        env_file = ".env"

settings = Settings()