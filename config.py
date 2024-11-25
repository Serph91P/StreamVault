import os
import secrets
from datetime import timedelta
from typing import Optional, Dict, Any
from urllib.parse import urljoin

# Default configuration values
DEFAULT_CONFIG: Dict[str, Any] = {
    'RECORDINGS_DIR': '/recordings/',
    'CELERY_BROKER_URL': 'amqp://user:password@rabbitmq:5672/',
    'CELERY_RESULT_BACKEND': 'redis://redis:6379/0',
    'EVENTSUB_WEBHOOK_PORT': 8080
}

def validate_config(config: Dict[str, Any]) -> None:
    required_vars = [
        'TWITCH_CLIENT_ID',
        'TWITCH_CLIENT_SECRET',
        'BASE_URL'
    ]
    missing = [var for var in required_vars if not config.get(var)]
    if missing:
        raise ValueError(f"Missing required configuration variables: {missing}")

class BaseConfig:
    BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))
    SECRET_KEY: str = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    
    # Database
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///' + os.path.join(BASE_DIR, 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    
    # Celery configurations
    CELERY_BROKER_URL: str = os.environ.get('CELERY_BROKER_URL', DEFAULT_CONFIG['CELERY_BROKER_URL'])
    CELERY_RESULT_BACKEND: str = os.environ.get('CELERY_RESULT_BACKEND', DEFAULT_CONFIG['CELERY_RESULT_BACKEND'])
    
    # Application specific configurations
    RECORDINGS_DIR: str = os.environ.get('RECORDINGS_DIR', DEFAULT_CONFIG['RECORDINGS_DIR'])
    
    # Twitch API configurations
    TWITCH_CLIENT_ID: Optional[str] = os.environ.get('TWITCH_CLIENT_ID')
    TWITCH_CLIENT_SECRET: Optional[str] = os.environ.get('TWITCH_CLIENT_SECRET')
    TWITCH_WEBHOOK_SECRET: Optional[str] = os.environ.get('TWITCH_WEBHOOK_SECRET')
    
    # URL configurations
    BASE_URL: Optional[str] = os.environ.get('BASE_URL')
    WEBHOOK_PATH: str = '/webhook/callback'
    EVENTSUB_WEBHOOK_PORT: int = int(os.environ.get('EVENTSUB_WEBHOOK_PORT', DEFAULT_CONFIG['EVENTSUB_WEBHOOK_PORT']))
    CALLBACK_URL: str = urljoin(BASE_URL, WEBHOOK_PATH) if BASE_URL else ''
    
    # Security configurations
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(days=1)
    
    def __init__(self):
        validate_config(self.__dict__)

class DevConfig(BaseConfig):
    DEBUG: bool = True
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = True
    SESSION_COOKIE_SECURE: bool = False
    
class ProdConfig(BaseConfig):
    DEBUG: bool = False
    TESTING: bool = False
    
class TestConfig(BaseConfig):
    TESTING: bool = True
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///:memory:'
    SESSION_COOKIE_SECURE: bool = False
    WTF_CSRF_ENABLED: bool = False

# Default configuration
Config = ProdConfig
