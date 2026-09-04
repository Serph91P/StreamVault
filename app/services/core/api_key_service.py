"""API key service.

Manages long-lived programmatic access tokens. Raw key values are returned to
the user exactly once at creation and never stored; only the SHA-256 hash is
persisted (mirrors the session token strategy in AuthService).
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ResolvedApiKey:
    """A validated API key bound to its currently authorized owner."""

    record: ApiKey
    owner: User


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key for DB lookup/storage.

    SECURITY NOTE (CodeQL py/weak-sensitive-data-hashing, false positive):
    SHA-256 is used here intentionally instead of bcrypt/argon2/scrypt.
    Slow KDFs exist to make brute-forcing low-entropy human-chosen passwords
    economically infeasible. The input here is NOT a password: it is a
    cryptographically random token produced by ``secrets.token_urlsafe(32)``
    (~256 bits of entropy, prefixed with ``sv_``). Brute-forcing such a token
    is computationally infeasible regardless of hash speed, so a slow KDF
    would only add per-request latency without improving security.
    SHA-256 also gives us constant-time DB lookups via an indexed hash column.
    Mirrors the strategy used by GitHub PATs, AWS access keys, Stripe secret
    keys, and StreamVault's own AuthService session tokens.
    """
    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()  # lgtm[py/weak-sensitive-data-hashing]
    # codeql[py/weak-sensitive-data-hashing]: input is a 256-bit random token, not a password.


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

    def resolve_active_owner(self, raw_key: str) -> Optional[ResolvedApiKey]:
        """Resolve a key and its current active owner through one policy seam.

        A key is usable only while its record is active and its owner remains
        active. The owner lookup is intentionally coupled to key validation so
        middleware cannot accidentally bypass current role or account policy.
        """
        if not raw_key or not raw_key.startswith(_KEY_PREFIX):
            return None
        try:
            resolved = (
                self.db.query(ApiKey, User)
                .join(User, ApiKey.user_id == User.id)
                .filter(ApiKey.key_hash == hash_api_key(raw_key))
                .filter(ApiKey.revoked_at.is_(None), User.is_active.is_(True))
                .first()
            )
            if not resolved:
                return None
            record, owner = resolved
            expires_at = record.expires_at
            if expires_at is not None:
                expires_at = (
                    expires_at.replace(tzinfo=timezone.utc)
                    if expires_at.tzinfo is None
                    else expires_at.astimezone(timezone.utc)
                )
                if expires_at <= datetime.now(timezone.utc):
                    return None
            # Best-effort touch; failure must not block the request.
            try:
                record.last_used_at = datetime.now(timezone.utc)
                self.db.add(record)
                self.db.commit()
            except Exception as touch_err:
                logger.debug(f"Could not update last_used_at: {touch_err}")
                self.db.rollback()
            return ResolvedApiKey(record=record, owner=owner)
        except Exception as e:
            logger.error(f"Error resolving API key: {e}")
            return None

    def validate(self, raw_key: str) -> Optional[ApiKey]:
        """Return an API-key record only when current owner policy permits it."""
        resolved = self.resolve_active_owner(raw_key)
        return resolved.record if resolved else None

    def get_user_for_key(self, raw_key: str) -> Optional[User]:
        resolved = self.resolve_active_owner(raw_key)
        return resolved.owner if resolved else None
