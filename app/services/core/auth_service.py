"""Authentication seam for passwords, legacy sessions, JWTs, and refresh rotation."""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jwt import InvalidTokenError
from sqlalchemy.orm import Session as DBSession

from app.models import RefreshToken, Session, User
from app.schemas.auth import UserCreate, UserResponse

logger = logging.getLogger("streamvault")

_DEFAULT_SCOPES = frozenset(
    {
        "admin",
        "settings:read",
        "settings:write",
        "recording:read",
        "recording:write",
        "api-keys:manage",
        "realtime:connect",
    }
)


class AuthConfigurationError(RuntimeError):
    """Raised when required authentication key material is absent or unsafe."""


class AuthTokenError(ValueError):
    """Raised when a bearer/access/refresh token cannot be accepted."""


class RefreshTokenReplayError(AuthTokenError):
    """Raised after a rotated refresh token is used again."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    family_id: str


def _hash_token(token: str) -> str:
    """Return the stable one-way lookup verifier for high-entropy tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class AuthService:
    """Own identity issuance and verification behind a narrow database-backed seam."""

    def __init__(self, db: DBSession, settings: Any | None = None):
        self.db = db
        if settings is None:
            from app.config.settings import get_settings

            settings = get_settings()
        self.settings = settings
        self.session_timeout_hours = 24

    @staticmethod
    def password_hasher(**overrides: Any) -> PasswordHasher:
        return PasswordHasher(**overrides)

    @property
    def _password_hasher(self) -> PasswordHasher:
        return self.password_hasher()

    def hash_password(self, password: str) -> str:
        return self._password_hasher.hash(password)

    async def admin_exists(self) -> bool:
        return bool(self.db.query(User).filter_by(is_admin=True).first())

    async def create_admin(self, user_data: UserCreate) -> UserResponse:
        admin = User(
            username=user_data.username,
            password=self.hash_password(user_data.password),
            is_admin=True,
            is_active=True,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        return UserResponse.model_validate(admin)

    async def validate_login(self, username: str, password: str) -> Optional[User]:
        user = self.db.query(User).filter_by(username=username).first()
        if not user or not getattr(user, "is_active", True):
            return None

        try:
            if user.password.startswith("$2"):
                valid = bcrypt.checkpw(
                    password.encode("utf-8"), user.password.encode("utf-8")
                )
                needs_rehash = valid
            else:
                valid = self._password_hasher.verify(user.password, password)
                needs_rehash = self._password_hasher.check_needs_rehash(user.password)
        except (InvalidHashError, VerifyMismatchError, ValueError):
            return None

        if not valid:
            return None
        if needs_rehash:
            user.password = self.hash_password(password)
            self.db.add(user)
            self.db.commit()
        return user

    def _jwt_config(self) -> tuple[str, str, str, str, int]:
        secret = getattr(self.settings, "AUTH_JWT_SECRET", None)
        algorithm = getattr(self.settings, "AUTH_JWT_ALGORITHM", "HS256")
        issuer = getattr(self.settings, "AUTH_JWT_ISSUER", "streamvault")
        audience = getattr(self.settings, "AUTH_JWT_AUDIENCE", "streamvault-api")
        access_minutes = getattr(self.settings, "AUTH_ACCESS_TOKEN_MINUTES", 15)
        if not isinstance(secret, str) or len(secret) < 32:
            raise AuthConfigurationError(
                "AUTH_JWT_SECRET must be at least 32 characters"
            )
        if algorithm != "HS256":
            raise AuthConfigurationError("AUTH_JWT_ALGORITHM must be HS256")
        if not issuer or not audience or access_minutes < 1:
            raise AuthConfigurationError(
                "JWT issuer, audience, and lifetime are required"
            )
        return secret, algorithm, issuer, audience, access_minutes

    @staticmethod
    def _user_scopes(user: User) -> frozenset[str]:
        return _DEFAULT_SCOPES if user.is_admin else frozenset({"recording:read"})

    def create_access_token(self, user: User) -> str:
        secret, algorithm, issuer, audience, access_minutes = self._jwt_config()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "typ": "access",
            "jti": uuid4().hex,
            "iat": now,
            "nbf": now,
            "exp": now + timedelta(minutes=access_minutes),
            "iss": issuer,
            "aud": audience,
            "roles": ["admin"] if user.is_admin else ["user"],
            "scp": sorted(self._user_scopes(user)),
        }
        return jwt.encode(payload, secret, algorithm=algorithm)

    def decode_access_token(self, token: str) -> dict[str, Any]:
        secret, algorithm, issuer, audience, _ = self._jwt_config()
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuer,
                options={"require": ["sub", "typ", "iat", "nbf", "exp", "iss", "aud"]},
            )
        except InvalidTokenError as error:
            raise AuthTokenError("Invalid access token") from error
        if claims.get("typ") != "access":
            raise AuthTokenError("Wrong token type")
        return claims

    def _refresh_expiry(self, now: datetime) -> tuple[datetime, datetime]:
        refresh_hours = getattr(self.settings, "AUTH_REFRESH_TOKEN_HOURS", 24)
        family_hours = getattr(self.settings, "AUTH_REFRESH_FAMILY_MAX_HOURS", 168)
        if refresh_hours < 1 or family_hours < refresh_hours:
            raise AuthConfigurationError("Refresh token lifetimes are invalid")
        return now + timedelta(hours=refresh_hours), now + timedelta(hours=family_hours)

    def _new_refresh_token(
        self,
        user: User,
        *,
        family_id: str | None = None,
        family_expires_at: datetime | None = None,
        parent_token_hash: str | None = None,
    ) -> tuple[RefreshToken, str]:
        now = datetime.now(timezone.utc)
        expires_at, new_family_expiry = self._refresh_expiry(now)
        family_expires_at = (
            _as_utc(family_expires_at) if family_expires_at else new_family_expiry
        )
        if family_expires_at <= now:
            raise AuthTokenError("Refresh family expired")
        raw_token = f"svr_{secrets.token_urlsafe(32)}"
        record = RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid4().hex,
            token_hash=_hash_token(raw_token),
            expires_at=min(expires_at, family_expires_at),
            family_expires_at=family_expires_at,
            parent_token_hash=parent_token_hash,
        )
        self.db.add(record)
        self.db.flush()
        return record, raw_token

    def issue_token_pair(self, user: User) -> TokenPair:
        if not getattr(user, "is_active", True):
            raise AuthTokenError("Inactive user")
        refresh, raw_refresh = self._new_refresh_token(user)
        self.db.commit()
        return TokenPair(
            access_token=self.create_access_token(user),
            refresh_token=raw_refresh,
            family_id=refresh.family_id,
        )

    def revoke_refresh_family(self, family_id: str) -> int:
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
            .update({RefreshToken.revoked_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def rotate_refresh_token(self, raw_token: str) -> TokenPair:
        token_hash = _hash_token(raw_token)
        refresh = self.db.query(RefreshToken).filter_by(token_hash=token_hash).first()
        now = datetime.now(timezone.utc)
        if not refresh:
            raise AuthTokenError("Invalid refresh token")
        if refresh.used_at is not None or refresh.revoked_at is not None:
            self.revoke_refresh_family(refresh.family_id)
            raise RefreshTokenReplayError("Refresh token replay detected")
        if (
            _as_utc(refresh.expires_at) < now
            or _as_utc(refresh.family_expires_at) < now
        ):
            self.revoke_refresh_family(refresh.family_id)
            raise AuthTokenError("Refresh token expired")
        user = self.db.query(User).filter_by(id=refresh.user_id).first()
        if not user or not getattr(user, "is_active", True):
            self.revoke_refresh_family(refresh.family_id)
            raise AuthTokenError("Refresh token user unavailable")

        refresh.used_at = now
        replacement, raw_replacement = self._new_refresh_token(
            user,
            family_id=refresh.family_id,
            family_expires_at=refresh.family_expires_at,
            parent_token_hash=refresh.token_hash,
        )
        self.db.commit()
        return TokenPair(
            access_token=self.create_access_token(user),
            refresh_token=raw_replacement,
            family_id=replacement.family_id,
        )

    async def create_session(self, user_id: int) -> str:
        """Create the temporary legacy opaque session during the JWT migration."""
        token = secrets.token_urlsafe(32)
        self.db.add(Session(user_id=user_id, token=_hash_token(token)))
        self.db.commit()
        return token

    async def validate_session(self, token: str) -> bool:
        return self.resolve_legacy_session(token) is not None

    def resolve_legacy_session(self, token: str) -> Optional[User]:
        session = self.db.query(Session).filter_by(token=_hash_token(token)).first()
        if not session:
            return None
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.session_timeout_hours
        )
        if session.created_at < cutoff:
            self.db.delete(session)
            self.db.commit()
            return None
        user = self.db.query(User).filter_by(id=session.user_id).first()
        return user if user and getattr(user, "is_active", True) else None

    async def refresh_session(self, token: str) -> bool:
        return self.resolve_legacy_session(token) is not None

    async def cleanup_expired_sessions(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=self.session_timeout_hours
        )
        expired = self.db.query(Session).filter(Session.created_at < cutoff).all()
        for session in expired:
            self.db.delete(session)
        if expired:
            self.db.commit()
        return len(expired)

    async def delete_session(self, token: str) -> bool:
        session = self.db.query(Session).filter_by(token=_hash_token(token)).first()
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True
