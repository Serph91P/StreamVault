from pydantic_settings import BaseSettings
from typing import Optional

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

    def __init__(self):
        super().__init__()
        self.WEBHOOK_URL = f"{self.BASE_URL}/eventsub/callback"

    class Config:
        env_file = ".env"

settings = Settings()