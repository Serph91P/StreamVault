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
from collections.abc import Callable
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger("streamvault")


class ProxyEncryption:
    """
    Handles encryption/decryption of proxy credentials.

    Uses Fernet symmetric encryption (AES-128 CBC with HMAC).

    Migration 032: Key management changed from environment variable to database.
    """

    def __init__(self, encryption_key: str | None = None):
        self._cipher: Fernet
        if encryption_key is None:
            self._initialize_cipher()
        else:
            self._cipher = Fernet(encryption_key.encode())

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

        try:
            self._cipher = bootstrap_proxy_identity(SessionLocal)._cipher
            return
        except Exception as e:
            logger.error(f"❌ Failed to load/save encryption key from database: {e}")
            # Fallback to environment variable for backward compatibility
            encryption_key = os.getenv("PROXY_ENCRYPTION_KEY")
            if encryption_key:
                logger.warning(
                    "⚠️ Using PROXY_ENCRYPTION_KEY from environment (deprecated)"
                )
                logger.warning("   Migration 032 should have moved this to database")
            else:
                raise RuntimeError("Persistent proxy identity unavailable") from e

        try:
            self._cipher = Fernet(
                encryption_key.encode()
                if isinstance(encryption_key, str)
                else encryption_key
            )
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
            encrypted_bytes: bytes = self._cipher.encrypt(plaintext.encode("utf-8"))
            encrypted_str = encrypted_bytes.decode("utf-8")

            logger.debug(
                f"🔒 Proxy URL encrypted successfully (length: {len(encrypted_str)})"
            )
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
            decrypted_bytes: bytes = self._cipher.decrypt(encrypted.encode("utf-8"))
            decrypted_str = decrypted_bytes.decode("utf-8")

            logger.debug("🔓 Proxy URL decrypted successfully")
            return decrypted_str

        except Exception as e:
            logger.error(f"❌ Decryption failed: {e}")
            logger.error("   This may indicate:")
            logger.error("   - Wrong encryption key in PROXY_ENCRYPTION_KEY")
            logger.error("   - Corrupted database entry")
            logger.error("   - Proxy was encrypted with different key")
            raise


def bootstrap_proxy_identity(session_factory: Callable[[], Session]) -> ProxyEncryption:
    """Persist one owner identity after migrations and prime future owned sessions."""
    from app.models import GlobalSettings

    try:
        with session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": 7_314_908_422},
                )
            settings = session.query(GlobalSettings).first()
            key = settings.proxy_encryption_key if settings else None
            if not key:
                key = Fernet.generate_key().decode()
                if settings is None:
                    settings = GlobalSettings(notifications_enabled=True)
                    session.add(settings)
                settings.proxy_encryption_key = key
            encryption = ProxyEncryption(key)
            session.commit()
    except Exception as error:
        raise RuntimeError("Persistent proxy identity unavailable") from error
    if isinstance(session_factory, sessionmaker):
        info = {
            **session_factory.kw.get("info", {}),
            "streamvault.proxy_encryption": encryption,
        }
        session_factory.configure(info=info)
    return encryption


# Singleton instance
_proxy_encryption = None


def get_cached_proxy_encryption(session: Session | None = None) -> ProxyEncryption:
    """Read a prepared identity without SQL, key generation or default construction."""
    cached = (
        session.info.get("streamvault.proxy_encryption")
        if session is not None
        else _proxy_encryption
    )
    if not isinstance(cached, ProxyEncryption):
        raise RuntimeError("Persistent proxy identity is not initialized")
    return cached


def get_proxy_encryption(session: Session | None = None) -> ProxyEncryption:
    """Use the attached catalogue identity, retaining the standalone adapter."""
    if session is not None:
        cached = session.info.get("streamvault.proxy_encryption")
        if isinstance(cached, ProxyEncryption):
            return cached
        from app.models import GlobalSettings

        # New attached proxies do not have their non-null encrypted field yet.
        with session.no_autoflush:
            stored = session.query(GlobalSettings.proxy_encryption_key).first()
        if stored is None or not stored.proxy_encryption_key:
            raise RuntimeError("Persistent proxy identity has not been initialized")
        encryption = ProxyEncryption(stored.proxy_encryption_key)
        session.info["streamvault.proxy_encryption"] = encryption
        return encryption
    global _proxy_encryption
    if _proxy_encryption is None:
        _proxy_encryption = ProxyEncryption()
    return _proxy_encryption
