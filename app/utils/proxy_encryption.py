"""
Proxy Credential Encryption Utility

Provides encryption/decryption for sensitive proxy credentials stored in database.
Uses Fernet symmetric encryption from cryptography library.

SECURITY: Proxy URLs contain sensitive credentials (username, password).
These MUST be encrypted in database to prevent exposure in case of database compromise.

Migration 032: Encryption key now stored in GlobalSettings.proxy_encryption_key
- BEFORE: PROXY_ENCRYPTION_KEY environment variable (manual setup required)
- AFTER: Auto-generated and stored in database (transparent, persistent)
- Key persists across container restarts
- No manual user intervention needed
"""

import os
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("streamvault")


class ProxyEncryption:
    """
    Handles encryption/decryption of proxy credentials.

    Uses Fernet symmetric encryption (AES-128 CBC with HMAC).

    Migration 032: Key management changed from environment variable to database.
    """

    def __init__(self):
        self._cipher = None
        self._initialize_cipher()

    def _initialize_cipher(self):
        """
        Initialize Fernet cipher with encryption key from database.

        Migration 032: Changed from environment variable to database storage.

        Flow:
        1. Try to read encryption key from GlobalSettings.proxy_encryption_key
        2. If not exists: Generate new Fernet key and save to database
        3. Initialize Fernet cipher

        Security: Key never logged to console or exposed in error messages.
        """
        from app.database import SessionLocal
        from app.models import GlobalSettings

        encryption_key = None

        try:
            with SessionLocal() as db:
                settings = db.query(GlobalSettings).first()

                if settings and settings.proxy_encryption_key:
                    encryption_key = settings.proxy_encryption_key
                    logger.info("🔐 Loaded proxy encryption key from database")
                else:
                    # Generate new key and save to database
                    logger.info("🔑 Generating new proxy encryption key...")
                    new_key = Fernet.generate_key()
                    encryption_key = new_key.decode("utf-8")

                    # Save to database
                    if not settings:
                        settings = GlobalSettings(notifications_enabled=True, proxy_encryption_key=encryption_key)
                        db.add(settings)
                    else:
                        settings.proxy_encryption_key = encryption_key

                    db.commit()
                    logger.info("✅ Proxy encryption key generated and saved to database")
                    logger.info("💡 Encryption key persists across container restarts")

        except Exception as e:
            logger.error(f"❌ Failed to load/save encryption key from database: {e}")
            # Fallback to environment variable for backward compatibility
            encryption_key = os.getenv("PROXY_ENCRYPTION_KEY")
            if encryption_key:
                logger.warning("⚠️ Using PROXY_ENCRYPTION_KEY from environment (deprecated)")
                logger.warning("   Migration 032 should have moved this to database")
            else:
                # Last resort: Generate ephemeral key (will cause data loss on restart)
                logger.error("❌ CRITICAL: No encryption key in database or environment!")
                logger.error("   Generating ephemeral key - proxies will be lost on restart")
                new_key = Fernet.generate_key()
                encryption_key = new_key.decode("utf-8")

        try:
            self._cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.debug("🔐 Proxy encryption initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize proxy encryption: {e}")
            raise

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt proxy URL with credentials.

        Args:
            plaintext: Proxy URL (e.g., "http://user:pass@host:port")

        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return plaintext

        try:
            encrypted_bytes = self._cipher.encrypt(plaintext.encode("utf-8"))
            encrypted_str = encrypted_bytes.decode("utf-8")

            logger.debug(f"🔒 Encrypted proxy URL: {plaintext[:20]}... → {encrypted_str[:20]}...")
            return encrypted_str

        except Exception as e:
            logger.error(f"❌ Encryption failed: {e}")
            raise

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt proxy URL to retrieve credentials.

        Args:
            encrypted: Encrypted proxy URL (base64 encoded)

        Returns:
            Decrypted proxy URL with credentials
        """
        if not encrypted:
            return encrypted

        try:
            decrypted_bytes = self._cipher.decrypt(encrypted.encode("utf-8"))
            decrypted_str = decrypted_bytes.decode("utf-8")

            logger.debug(f"🔓 Decrypted proxy URL: {encrypted[:20]}... → {decrypted_str[:20]}...")
            return decrypted_str

        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            logger.error("   This may indicate:")
            logger.error("   - Wrong encryption key in PROXY_ENCRYPTION_KEY")
            logger.error("   - Corrupted database entry")
            logger.error("   - Proxy was encrypted with different key")
            raise


# Singleton instance
_proxy_encryption = None


def get_proxy_encryption() -> ProxyEncryption:
    """Get singleton instance of ProxyEncryption"""
    global _proxy_encryption
    if _proxy_encryption is None:
        _proxy_encryption = ProxyEncryption()
    return _proxy_encryption
