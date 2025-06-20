from pydantic_settings import BaseSettings
from typing import Optional
import secrets
from typing import List
import logging
import base64

logger = logging.getLogger("streamvault")

def generate_vapid_keys():
    """Generate VAPID keys automatically if not provided"""
    try:
        from pywebpush import Vapid
        
        # Generate VAPID keys using pywebpush
        vapid = Vapid()
        vapid.generate_keys()
        
        private_key = vapid.private_key.private_bytes_raw()
        public_key = vapid.public_key.public_bytes_raw()
        
        # Encode as base64url (without padding) - pywebpush standard
        private_key_b64 = base64.urlsafe_b64encode(private_key).decode().rstrip('=')
        public_key_b64 = base64.urlsafe_b64encode(public_key).decode().rstrip('=')
        
        logger.info("✅ VAPID keys auto-generated successfully")
        return public_key_b64, private_key_b64
        
    except ImportError:
        logger.warning("⚠️ pywebpush library not available for VAPID key generation")
        logger.info("💡 Install with: pip install pywebpush")
        return None, None
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-generate VAPID keys: {e}")
        return None, None

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
    
    # Proxy settings for Streamlink
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None
    
    # PWA and Push Notification settings (server-global, not per-user)
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_CLAIMS_SUB: str = "mailto:admin@streamvault.local"
    
    @property
    def has_push_notifications_configured(self) -> bool:
        """Check if push notifications are properly configured"""
        return bool(self.VAPID_PUBLIC_KEY and self.VAPID_PRIVATE_KEY)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.WEBHOOK_URL:
            base = self.BASE_URL.rstrip('/')
            self.WEBHOOK_URL = base

        # Load and auto-generate VAPID keys if needed
        self._load_or_generate_vapid_keys()
    
    def _load_or_generate_vapid_keys(self):
        """Load VAPID keys from database or auto-generate if not found"""
        try:
            # Only try to load from database if not provided via environment
            if not self.VAPID_PUBLIC_KEY or not self.VAPID_PRIVATE_KEY:
                # Import here to avoid circular imports
                from app.services.system_config_service import system_config_service
                
                # Try to load from database
                stored_keys = system_config_service.get_vapid_keys()
                
                if stored_keys['public_key'] and stored_keys['private_key']:
                    logger.info("🔑 Loading VAPID keys from database")
                    self.VAPID_PUBLIC_KEY = stored_keys['public_key']
                    self.VAPID_PRIVATE_KEY = stored_keys['private_key']
                    if stored_keys['claims_sub']:
                        self.VAPID_CLAIMS_SUB = stored_keys['claims_sub']
                else:
                    # Generate new keys and store them
                    self._auto_generate_and_store_vapid_keys()
                    
        except Exception as e:
            logger.warning(f"⚠️ Could not load VAPID keys from database: {e}")
            logger.info("💡 Will try to auto-generate keys...")
            self._auto_generate_and_store_vapid_keys()
    
    def _auto_generate_and_store_vapid_keys(self):
        """Auto-generate VAPID keys and store them in database"""
        try:
            logger.info("🔑 Generating new VAPID keys...")
            
            public_key, private_key = generate_vapid_keys()
            if public_key and private_key:
                self.VAPID_PUBLIC_KEY = public_key
                self.VAPID_PRIVATE_KEY = private_key
                
                # Store in database for persistence
                try:
                    from app.services.system_config_service import system_config_service
                    system_config_service.set_vapid_keys(
                        public_key, 
                        private_key, 
                        self.VAPID_CLAIMS_SUB
                    )
                    logger.info("✅ VAPID keys generated and stored in database!")
                    logger.info("� Keys will persist across container restarts")
                    
                except Exception as db_error:
                    logger.warning(f"⚠️ Generated VAPID keys but could not store in database: {db_error}")
                    logger.info("🔑 Keys will work for this session but won't persist")
            else:
                logger.warning("⚠️ Could not auto-generate VAPID keys")
                logger.info("💡 Push notifications will not be available")
                
        except Exception as e:
            logger.warning(f"⚠️ VAPID key auto-generation failed: {e}")

    class Config:
        env_file = ".env"

settings = Settings()