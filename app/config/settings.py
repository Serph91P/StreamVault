from pydantic_settings import BaseSettings
from typing import Optional
import secrets
from typing import List
import logging
import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from urllib.parse import urlparse
from typing import Set

logger = logging.getLogger("streamvault")

def generate_vapid_keys():
    """Generate VAPID keys automatically if not provided"""
    try:
        # First try using py_vapid
        from py_vapid import Vapid
        
        vapid = Vapid()
        vapid.generate_keys()
        
        # Different versions of py_vapid have different APIs
        try:
            # Try newer API first
            private_key_der = vapid.private_key_bytes()
            public_key_uncompressed = vapid.public_key_bytes()
        except AttributeError:
            # Try older API - access the actual cryptography keys
            private_key_der = vapid.private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_key_uncompressed = vapid.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
          # Convert to base64url format for storage and the frontend API
        try:
            from py_vapid.utils import b64urlencode
            if isinstance(public_key_uncompressed, str):
                # If it's already a string, assume it's already encoded
                public_key_b64url = public_key_uncompressed
            else:
                public_key_b64url = b64urlencode(public_key_uncompressed).decode('utf-8')
        except ImportError:
            # Fallback if b64urlencode is not available
            if isinstance(public_key_uncompressed, str):
                public_key_b64url = public_key_uncompressed
            else:
                public_key_b64url = base64.urlsafe_b64encode(public_key_uncompressed).decode('utf-8').rstrip('=')
        
        # Store the private key as base64 for database storage
        private_key_b64 = base64.b64encode(private_key_der).decode('utf-8')
        
        logger.info("✅ VAPID keys auto-generated successfully using py_vapid")
        logger.debug(f"Public key (b64url): {public_key_b64url[:20]}...")
        logger.debug(f"Private key stored as base64 (length: {len(private_key_b64)})")
        
        return public_key_b64url, private_key_b64
        
    except ImportError:
        logger.warning("⚠️ py_vapid library not available, trying direct cryptography approach")
        return _generate_vapid_keys_direct()
    except Exception as e:
        logger.warning(f"⚠️ py_vapid failed, trying direct cryptography approach: {e}")
        return _generate_vapid_keys_direct()

def _generate_vapid_keys_direct():
    """Generate VAPID keys directly using cryptography library"""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        
        # Generate P-256 private key (SECP256R1)
        private_key = ec.generate_private_key(ec.SECP256R1())
        
        # Get private key in DER format
        private_key_der = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Get public key in uncompressed format
        public_key_uncompressed = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
          # Convert to base64url format for frontend
        if isinstance(public_key_uncompressed, str):
            public_key_b64url = public_key_uncompressed
        else:
            public_key_b64url = base64.urlsafe_b64encode(public_key_uncompressed).decode('utf-8').rstrip('=')
        
        # Store the private key as base64 for database storage
        if isinstance(private_key_der, str):
            private_key_b64 = private_key_der
        else:
            private_key_b64 = base64.b64encode(private_key_der).decode('utf-8')
        
        logger.info("✅ VAPID keys auto-generated successfully using direct cryptography")
        logger.debug(f"Public key (b64url): {public_key_b64url[:20]}...")
        logger.debug(f"Private key stored as base64 (length: {len(private_key_b64)})")
        
        return public_key_b64url, private_key_b64
        
    except Exception as e:
        logger.error(f"❌ Failed to generate VAPID keys directly: {e}")
        logger.info("💡 Push notifications will not be available")
        return None, None

class Settings(BaseSettings):
    TWITCH_APP_ID: str
    TWITCH_APP_SECRET: str
    BASE_URL: str
    WEBHOOK_URL: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    # Base directory for the application
    BASE_DIR: str = str(Path(__file__).parent.parent.parent.absolute())
    LOG_LEVEL: str = "INFO"
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    EVENTSUB_PORT: int = 8080
    EVENTSUB_SECRET: str = secrets.token_urlsafe(32)
    APPRISE_URLS: List[str] = []
    
    # Proxy settings for Streamlink
    HTTP_PROXY: Optional[str] = None
    HTTPS_PROXY: Optional[str] = None
    
    # Artwork and metadata directory (within recordings directory)
    ARTWORK_BASE_PATH: str = "/recordings/.artwork"
    
    # PWA and Push Notification settings (server-global, not per-user)
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_CLAIMS_SUB: str = "mailto:admin@streamvault.local"
    
    # CORS settings
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    CORS_MAX_AGE: int = 86400  # 24 hours
    
    # Additional allowed origins (comma-separated in env)
    CORS_ADDITIONAL_ORIGINS: str = ""
    
    # Security settings
    SECURE_HEADERS_ENABLED: bool = True
    HSTS_MAX_AGE: int = 31536000  # 1 year
    CONTENT_SECURITY_POLICY: Optional[str] = None
    
    @property
    def allowed_origins(self) -> List[str]:
        """
        Generate allowed origins based on BASE_URL and additional configured origins.
        This ensures the app works correctly with the configured domain.
        """
        origins = set()
        
        # Always allow the BASE_URL origin
        try:
            parsed_url = urlparse(self.BASE_URL)
            origin = f"{parsed_url.scheme}://{parsed_url.netloc}"
            origins.add(origin)
            
            # Also add without port if standard ports
            if parsed_url.port in (80, 443, None):
                origins.add(f"{parsed_url.scheme}://{parsed_url.hostname}")
            
            # Add www variant if not present
            if parsed_url.hostname and not parsed_url.hostname.startswith('www.'):
                origins.add(f"{parsed_url.scheme}://www.{parsed_url.hostname}")
                if parsed_url.port:
                    origins.add(f"{parsed_url.scheme}://www.{parsed_url.hostname}:{parsed_url.port}")
            
        except Exception as e:
            logger.warning(f"Could not parse BASE_URL for CORS: {e}")
        
        # Add localhost origins for development
        if os.getenv("ENVIRONMENT") == "development":
            origins.update([
                "http://localhost:5173",  # Vite dev server
                "http://localhost:3000",  # Alternative dev server
                "http://localhost:7000",  # Production port locally
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:7000"
            ])
        
        # Add any additional origins from environment
        if self.CORS_ADDITIONAL_ORIGINS:
            additional = [o.strip() for o in self.CORS_ADDITIONAL_ORIGINS.split(",") if o.strip()]
            origins.update(additional)
        
        # Convert to sorted list for consistent ordering
        return sorted(list(origins))
    
    @property
    def has_push_notifications_configured(self) -> bool:
        """Check if push notifications are properly configured"""
        return bool(self.VAPID_PUBLIC_KEY and self.VAPID_PRIVATE_KEY)
    
    @property
    def is_secure(self) -> bool:
        """Check if running in secure (HTTPS) mode"""
        return self.BASE_URL.startswith("https://")
    
    @property
    def domain(self) -> str:
        """Extract domain from BASE_URL"""
        try:
            parsed = urlparse(self.BASE_URL)
            return parsed.hostname or "localhost"
        except:
            return "localhost"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.WEBHOOK_URL:
            base = self.BASE_URL.rstrip('/')
            self.WEBHOOK_URL = base

        # Load and auto-generate VAPID keys if needed
        self._load_or_generate_vapid_keys()
        
        # Log CORS configuration
        logger.info(f"🌐 CORS configured for origins: {', '.join(self.allowed_origins)}")
        logger.info(f"🔒 Secure mode: {'Yes' if self.is_secure else 'No'}")
    
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

def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings