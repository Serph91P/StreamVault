from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TWITCH_APP_ID: str
    TWITCH_APP_SECRET: str
    BASE_URL: str
    WEBHOOK_URL: str = None

    def __init__(self):
        super().__init__()
        self.WEBHOOK_URL = f"{self.BASE_URL}/eventsub"

settings = Settings()
