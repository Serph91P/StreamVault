"""API key service.

Manages long-lived programmatic access tokens. Raw key values are returned to
the user exactly once at creation and never stored; only the SHA-256 hash is
persisted (mirrors the session token strategy in AuthService).
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session as DBSession

from app.models import ApiKey, User

logger = logging.getLogger("streamvault")

# Raw API key format: "sv_<43-char urlsafe random>" — distinguishable prefix
# avoids confusion with session cookies / Twitch tokens in logs and config.
_KEY_PREFIX = "sv_"
_KEY_RANDOM_BYTES = 32  # token_urlsafe(32) -> 43 chars
_PREFIX_DISPLAY_LEN = 10  # Number of chars stored for UI display (e.g. "sv_abcdef…")


def hash_api_key(raw_key: str) -> str:
    """SECURITY: SHA-256 the raw key before DB lookup/storage (CWE-312)."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class ApiKeyService:
    def __init__(self, db: DBSession):
        self.db = db

    @staticmethod
    def generate_key() -> str:
        """Generate a new raw API key value."""
        return f"{_KEY_PREFIX}{secrets.token_urlsafe(_KEY_RANDOM_BYTES)}"

    def create(self, user_id: int, name: str) -> tuple[ApiKey, str]:
        """Create and persist a new API key. Returns (record, raw_key)."""
        raw_key = self.generate_key()
        record = ApiKey(
            user_id=user_id,
            name=name.strip(),
            key_hash=hash_api_key(raw_key),
            key_prefix=raw_key[:_PREFIX_DISPLAY_LEN],
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info(
            f"API key created (id={record.id}, name={record.name!r}, user_id={user_id})"
        )
        return record, raw_key

    def list_for_user(self, user_id: int) -> List[ApiKey]:
        return (
            self.db.query(ApiKey)
            .filter(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )

    def list_all(self) -> List[ApiKey]:
        return self.db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()

    def revoke(self, key_id: int, user_id: Optional[int] = None) -> bool:
        """Revoke a key. If user_id is given, scope to that user.

        Returns True if a record was revoked, False if not found / already revoked.
        """
        q = self.db.query(ApiKey).filter(ApiKey.id == key_id)
        if user_id is not None:
            q = q.filter(ApiKey.user_id == user_id)
        record = q.first()
        if not record:
            return False
        if record.revoked_at is not None:
            return False
        record.revoked_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.commit()
        logger.info(f"API key revoked (id={record.id}, name={record.name!r})")
        return True

    def validate(self, raw_key: str) -> Optional[ApiKey]:
        """Validate a raw API key. Returns the active ApiKey record or None.

        Touches `last_used_at` on success. Validation is constant-time-safe
        because the lookup is by SHA-256 hash (no string comparison on secret).
        """
        if not raw_key or not raw_key.startswith(_KEY_PREFIX):
            return None
        try:
            record = (
                self.db.query(ApiKey)
                .filter(ApiKey.key_hash == hash_api_key(raw_key))
                .first()
            )
            if not record or record.revoked_at is not None:
                return None
            # Best-effort touch; failure must not block the request.
            try:
                record.last_used_at = datetime.now(timezone.utc)
                self.db.add(record)
                self.db.commit()
            except Exception as touch_err:
                logger.debug(f"Could not update last_used_at: {touch_err}")
                self.db.rollback()
            return record
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None

    def get_user_for_key(self, raw_key: str) -> Optional[User]:
        record = self.validate(raw_key)
        if not record:
            return None
        return self.db.query(User).filter(User.id == record.user_id).first()
