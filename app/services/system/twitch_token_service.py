"""Application-owned Twitch user credentials; closed DB workers precede HTTP I/O.

Keep manual-token/environment/OAuth precedence, expiry budgets and recording CAS
invalidation. This is user authentication, not Twitch's application-token cache.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import count
from typing import TypeVar

from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config.settings import Settings, get_settings
from app.models import GlobalSettings
from app.services.http_client import HTTPClientError, HTTPPolicy, ManagedHTTPClient
from app.services.system.supervisor import TaskSupervisor
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.proxy_encryption import ProxyEncryption as ProxyEncryption
from app.utils.proxy_encryption import get_proxy_encryption

logger = logging.getLogger("streamvault")
T = TypeVar("T")


@dataclass(frozen=True)
class RecordingStoredTokenVersion:
    """Database token identity used for compare-and-set invalidation."""

    settings_id: int | None
    encrypted_token: str = field(repr=False)
    encrypted_refresh_token: str | None = field(repr=False)
    expires_at: datetime | None


@dataclass(frozen=True)
class RecordingTokenResolution:
    """Result of resolving and live-validating recording authentication."""

    token: str | None = field(repr=False)
    source: str | None
    live_valid: bool
    definitive_invalid: bool
    reason: str
    stored_version: RecordingStoredTokenVersion | None = field(default=None, repr=False)


@dataclass(frozen=True)
class TwitchTokenState:
    """Private scalar catalogue value, never a live ORM/session identity."""

    id: int | None
    twitch_access_token: str | None = field(repr=False)
    twitch_refresh_token: str | None = field(repr=False)
    twitch_token_expires_at: datetime | None


class TwitchTokenService:
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
    EXPIRATION_BUFFER_SECONDS = 3600
    MANUAL_TOKEN_NOTIFICATION_BUFFER_SECONDS = 24 * 3600
    DEFAULT_MANUAL_TOKEN_EXPIRES_IN_SECONDS = 60 * 24 * 3600
    RECORDING_VALIDATION_TIMEOUT_SECONDS = 3.0
    RECORDING_INVALIDATED_TOKEN_EXPIRY = datetime(1970, 1, 1)

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        settings: Settings | None = None,
        on_tokens_changed: Callable[[], Awaitable[object]] | None = None,
        notify_expiry: Callable[[str, str], Awaitable[object]] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.settings = settings if settings is not None else get_settings()
        self._on_tokens_changed = on_tokens_changed
        self._notify_expiry = notify_expiry
        self._refresh_lock = asyncio.Lock()
        self._last_expiry_notification_at: datetime | None = None
        self._supervisor = TaskSupervisor("twitch-user-credentials")
        self._operation_ids = count()
        self._close_task: asyncio.Task[None] | None = None
        # Retain aiohttp's former 300s total/30s socket-connect envelope.
        # Recording validation additionally retains its complete 3s deadline.
        self.http_client = ManagedHTTPClient(
            HTTPPolicy(
                connect_timeout=30,
                read_timeout=300,
                write_timeout=300,
                total_timeout=300,
            )
        )

    async def _operation(self, name: str, work: Coroutine[object, object, T]) -> T:
        if self._close_task is not None:
            work.close()
            raise RuntimeError("Twitch credential service is closed")
        owned_name = f"{name}:{next(self._operation_ids)}"
        task = self._supervisor.create_task(owned_name, work)
        try:
            return await task
        finally:
            await self._supervisor.cancel_task(owned_name)

    async def close(self) -> None:
        if self._close_task is None:
            self._close_task = asyncio.create_task(
                self._close_resources(),
                name="streamvault:twitch-user-credentials:close",
            )
        task = self._close_task
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _close_resources(self) -> None:
        try:
            await self._supervisor.shutdown()
        finally:
            await self.http_client.close()

    async def _in_db(self, operation: Callable[[Session], T]) -> T:
        def run() -> T:
            from app.database import SessionLocal

            with (self._session_factory or SessionLocal)() as db:
                return operation(db)

        return await run_in_thread_pool(run)

    async def get_state(self) -> TwitchTokenState | None:
        return await self._operation("read-state", self._read_state())

    async def _read_state(self) -> TwitchTokenState | None:
        def read(db: Session) -> TwitchTokenState | None:
            row = db.query(GlobalSettings).first()
            if row is None:
                return None
            return TwitchTokenState(
                getattr(row, "id", None),
                row.twitch_access_token,
                row.twitch_refresh_token,
                row.twitch_token_expires_at,
            )

        return await self._in_db(read)

    async def _decrypt(self, encrypted: str) -> str:
        return await self._in_db(lambda db: get_proxy_encryption(db).decrypt(encrypted))

    @staticmethod
    def _stored_token_version(
        state: TwitchTokenState,
    ) -> RecordingStoredTokenVersion | None:
        if not state.twitch_access_token:
            return None
        return RecordingStoredTokenVersion(
            state.id,
            state.twitch_access_token,
            state.twitch_refresh_token,
            state.twitch_token_expires_at,
        )

    def _is_token_valid(self, state: TwitchTokenState) -> bool:
        expires_at = state.twitch_token_expires_at
        return expires_at is not None and datetime.utcnow() < expires_at - timedelta(
            seconds=self.EXPIRATION_BUFFER_SECONDS
        )

    @staticmethod
    def _state_conditions(state: TwitchTokenState) -> list[ColumnElement[bool]]:
        conditions = [
            GlobalSettings.twitch_access_token == state.twitch_access_token,
            GlobalSettings.twitch_refresh_token == state.twitch_refresh_token,
            GlobalSettings.twitch_token_expires_at == state.twitch_token_expires_at,
        ]
        if state.id is not None:
            conditions.append(GlobalSettings.id == state.id)
        return conditions

    async def _select_token(
        self, *, notify: bool
    ) -> tuple[str | None, str | None, RecordingStoredTokenVersion | None]:
        state = await self._read_state()
        if state and state.twitch_access_token and not state.twitch_refresh_token:
            valid = self._is_token_valid(state)
            if notify:
                await self._send_expiry_notification_if_needed(state, expired=not valid)
            if valid:
                return (
                    await self._decrypt(state.twitch_access_token),
                    "database_manual",
                    self._stored_token_version(state),
                )
        if self.settings.TWITCH_OAUTH_TOKEN:
            return self.settings.TWITCH_OAUTH_TOKEN, "environment", None
        if state and state.twitch_refresh_token:
            if self._is_token_valid(state):
                token = (
                    await self._decrypt(state.twitch_access_token)
                    if state.twitch_access_token
                    else None
                )
                return (
                    token,
                    "database_oauth",
                    self._stored_token_version(state) if token else None,
                )
            refreshed = False
            async with self._refresh_lock:
                state = await self._read_state()
                if state is None:
                    return None, None, None
                if self._is_token_valid(state):
                    token = (
                        await self._decrypt(state.twitch_access_token)
                        if state.twitch_access_token
                        else None
                    )
                    source = "database_oauth"
                    version = self._stored_token_version(state) if token else None
                else:
                    source = "oauth_refresh"
                    publication = await self._refresh_access_token(state)
                    token, version = (
                        publication if publication is not None else (None, None)
                    )
                    refreshed = token is not None
            # A config regeneration reads credentials again; never retain the
            # refresh lock while invoking that consumer.
            if refreshed:
                await self._tokens_changed()
            return token, source, version
        return None, None, None

    async def resolve_recording_token(self) -> RecordingTokenResolution:
        return await self._operation(
            "resolve-recording", self._resolve_recording_token()
        )

    async def _resolve_recording_token(self) -> RecordingTokenResolution:
        source = None
        try:
            async with asyncio.timeout(self.RECORDING_VALIDATION_TIMEOUT_SECONDS):
                token, source, version = await self._select_token(notify=False)
                if source == "environment" and token:
                    token = token.strip()
                if not token:
                    return RecordingTokenResolution(
                        None, source, False, False, "credential_unavailable", version
                    )
                validation = await self._validate_recording_token(token)
                if validation == "valid":
                    if version is not None:
                        current = await self._read_state()
                        unchanged = (
                            current is not None
                            and self._stored_token_version(current) == version
                        )
                    else:
                        unchanged = (
                            source == "environment"
                            and (self.settings.TWITCH_OAUTH_TOKEN or "").strip()
                            == token
                        )
                    if not unchanged:
                        return RecordingTokenResolution(
                            None, source, False, False, "credential_changed", version
                        )
                    return RecordingTokenResolution(
                        token, source, True, False, "validated", version
                    )
                if validation == "invalid":
                    if version is not None:
                        await self._invalidate_recording_token(version)
                    return RecordingTokenResolution(
                        None, source, False, True, "validation_invalid", version
                    )
                return RecordingTokenResolution(
                    None, source, False, False, "validation_transient", version
                )
        except TimeoutError:
            logger.warning("Twitch recording token validation timed out")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Twitch recording token validation failed transiently")
        return RecordingTokenResolution(
            None, source, False, False, "validation_transient"
        )

    async def _validate_recording_token(self, access_token: str) -> str:
        try:
            async with asyncio.timeout(self.RECORDING_VALIDATION_TIMEOUT_SECONDS):
                reply = await self.http_client.request(
                    "GET",
                    self.VALIDATE_URL,
                    headers={"Authorization": f"OAuth {access_token}"},
                )
                if reply.status_code != 200:
                    return "transient"
                payload = json.loads(reply.body)
                expires_in = (
                    payload.get("expires_in") if isinstance(payload, dict) else None
                )
                if (
                    not isinstance(payload, dict)
                    or not isinstance(payload.get("client_id"), str)
                    or not payload["client_id"].strip()
                    or not isinstance(expires_in, int)
                    or isinstance(expires_in, bool)
                    or expires_in < 0
                ):
                    return "transient"
                return "valid"
        except asyncio.CancelledError:
            raise
        except HTTPClientError as error:
            return "invalid" if error.status_code in (401, 403) else "transient"
        except Exception:
            return "transient"

    async def invalidate_recording_token(
        self, version: RecordingStoredTokenVersion
    ) -> bool:
        return await self._operation(
            "invalidate-recording", self._invalidate_recording_token(version)
        )

    async def _invalidate_recording_token(
        self, version: RecordingStoredTokenVersion
    ) -> bool:
        def invalidate(db: Session) -> bool:
            conditions = [
                GlobalSettings.twitch_access_token == version.encrypted_token,
                GlobalSettings.twitch_token_expires_at == version.expires_at,
                GlobalSettings.twitch_refresh_token == version.encrypted_refresh_token,
            ]
            if version.settings_id is not None:
                conditions.append(GlobalSettings.id == version.settings_id)
            try:
                updated = (
                    db.query(GlobalSettings)
                    .filter(*conditions)
                    .update(
                        {
                            GlobalSettings.twitch_token_expires_at: self.RECORDING_INVALIDATED_TOKEN_EXPIRY
                        },
                        synchronize_session=False,
                    )
                )
                if updated == 1:
                    db.commit()
                    logger.warning("Stored Twitch token was invalidated")
                    return True
                db.rollback()
                logger.info("Skipped invalidating a concurrently replaced Twitch token")
            except Exception:
                db.rollback()
                logger.warning("Could not conditionally invalidate stored Twitch token")
            return False

        return await self._in_db(invalidate)

    async def get_valid_access_token(self) -> str | None:
        return await self._operation("get-access-token", self._get_valid_access_token())

    async def _get_valid_access_token(self) -> str | None:
        try:
            token, _, _ = await self._select_token(notify=True)
            return token
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("Error getting valid Twitch access token")
            return self.settings.TWITCH_OAUTH_TOKEN

    async def _refresh_access_token(
        self, state: TwitchTokenState
    ) -> tuple[str, RecordingStoredTokenVersion] | None:
        try:
            if not state.twitch_refresh_token:
                return None
            refresh_token = await self._decrypt(state.twitch_refresh_token)
            if not refresh_token:
                return None
            reply = await self.http_client.request(
                "POST",
                self.TOKEN_URL,
                data={
                    "client_id": self.settings.TWITCH_APP_ID,
                    "client_secret": self.settings.TWITCH_APP_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
            if reply.status_code != 200:
                return None
            payload = json.loads(reply.body)
            if not isinstance(payload, dict):
                return None
            access_token = payload.get("access_token")
            new_refresh_token = payload.get("refresh_token")
            expires_in = payload.get("expires_in", 14400)
            if not isinstance(access_token, str) or not access_token:
                return None
            if not isinstance(expires_in, (int, float)):
                return None
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            def publish(db: Session) -> RecordingStoredTokenVersion | None:
                try:
                    encryption = get_proxy_encryption(db)
                    encrypted_access = encryption.encrypt(access_token)
                    encrypted_refresh = state.twitch_refresh_token
                    values: dict[str, str | datetime] = {
                        "twitch_access_token": encrypted_access,
                        "twitch_token_expires_at": expires_at,
                    }
                    if (
                        isinstance(new_refresh_token, str)
                        and new_refresh_token
                        and new_refresh_token != refresh_token
                    ):
                        encrypted_refresh = encryption.encrypt(new_refresh_token)
                        values["twitch_refresh_token"] = encrypted_refresh
                    updated = (
                        db.query(GlobalSettings)
                        .filter(*self._state_conditions(state))
                        .update(
                            {key: value for key, value in values.items()},
                            synchronize_session=False,
                        )
                    )
                    if updated == 1:
                        db.commit()
                        return RecordingStoredTokenVersion(
                            state.id, encrypted_access, encrypted_refresh, expires_at
                        )
                    db.rollback()
                    return None
                except Exception:
                    db.rollback()
                    logger.error("Could not publish refreshed Twitch credentials")
                    return None

            version = await self._in_db(publish)
            return (access_token, version) if version is not None else None
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("Error refreshing Twitch access token")
            return None

    async def _tokens_changed(self) -> None:
        if self._on_tokens_changed is not None:
            try:
                await self._on_tokens_changed()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning(
                    "Could not regenerate Streamlink credential configuration"
                )

    async def store_oauth_tokens(
        self, access_token: str, refresh_token: str, expires_in: int | float = 14400
    ) -> bool:
        return await self._operation(
            "store-oauth",
            self._store_oauth_tokens(access_token, refresh_token, expires_in),
        )

    async def _store_oauth_tokens(
        self, access_token: str, refresh_token: str, expires_in: int | float
    ) -> bool:
        def store(db: Session) -> bool:
            try:
                row = db.query(GlobalSettings).first()
                if row is None:
                    return False
                encryption = get_proxy_encryption(db)
                row.twitch_refresh_token = encryption.encrypt(refresh_token)
                row.twitch_access_token = encryption.encrypt(access_token)
                row.twitch_token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in
                )
                db.commit()
                return True
            except Exception:
                db.rollback()
                logger.error("Could not store Twitch OAuth credentials")
                return False

        success = await self._in_db(store)
        if success:
            await self._tokens_changed()
        return success

    async def store_manual_access_token(
        self, access_token: str
    ) -> tuple[bool, dict[str, object] | None]:
        return await self._operation(
            "store-manual", self._store_manual_access_token(access_token)
        )

    async def _store_manual_access_token(
        self, access_token: str
    ) -> tuple[bool, dict[str, object] | None]:
        clean_token = access_token.strip()
        if clean_token.lower().startswith("oauth:"):
            clean_token = clean_token.split(":", 1)[1].strip()
        if clean_token.lower().startswith("oauth "):
            clean_token = clean_token.split(" ", 1)[1].strip()
        if not clean_token:
            return False, None
        validation = await self._validate_token(clean_token)
        if not validation:
            return False, None
        try:
            expires_at = self._manual_expiration(validation)
        except (ValueError, TypeError, OverflowError):
            return False, validation

        def store(db: Session) -> bool:
            try:
                row = db.query(GlobalSettings).first()
                if row is None:
                    return False
                row.twitch_access_token = get_proxy_encryption(db).encrypt(clean_token)
                row.twitch_token_expires_at = expires_at
                row.twitch_refresh_token = None
                db.commit()
                return True
            except Exception:
                db.rollback()
                logger.error("Could not store manual Twitch credentials")
                return False

        success = await self._in_db(store)
        if success:
            await self._tokens_changed()
        return success, validation

    def _manual_expiration(self, validation: dict[str, object]) -> datetime:
        value = validation.get("expires_in") or 0
        if not isinstance(value, (str, int, float)):
            raise ValueError("Invalid Twitch token expiration")
        seconds = int(value)
        if seconds <= 0:
            seconds = self.DEFAULT_MANUAL_TOKEN_EXPIRES_IN_SECONDS
        return datetime.utcnow() + timedelta(seconds=seconds)

    async def revalidate_stored_manual_token(self, state: TwitchTokenState) -> bool:
        return await self._operation(
            "revalidate-manual", self._revalidate_stored_manual_token(state)
        )

    async def _revalidate_stored_manual_token(self, state: TwitchTokenState) -> bool:
        if not state or not state.twitch_access_token or state.twitch_refresh_token:
            return False
        if state.twitch_token_expires_at == self.RECORDING_INVALIDATED_TOKEN_EXPIRY:
            return False
        try:
            access_token = await self._decrypt(state.twitch_access_token)
            if not access_token:
                return False
            validation = await self._validate_token(access_token)
            if not validation:
                return False
            expires_at = self._manual_expiration(validation)

            def store(db: Session) -> bool:
                try:
                    updated = (
                        db.query(GlobalSettings)
                        .filter(*self._state_conditions(state))
                        .update(
                            {GlobalSettings.twitch_token_expires_at: expires_at},
                            synchronize_session=False,
                        )
                    )
                    if updated == 1:
                        db.commit()
                        return True
                    db.rollback()
                    return False
                except Exception:
                    db.rollback()
                    logger.error("Could not publish Twitch token revalidation")
                    return False

            return await self._in_db(store)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Could not revalidate stored manual Twitch credentials")
            return False

    async def _send_expiry_notification_if_needed(
        self, state: TwitchTokenState, expired: bool = False
    ) -> None:
        expires_at = state.twitch_token_expires_at
        if not expires_at:
            return
        now = datetime.utcnow()
        if (
            self._last_expiry_notification_at
            and now - self._last_expiry_notification_at < timedelta(hours=12)
        ):
            return
        if (
            not expired
            and (expires_at - now).total_seconds()
            > self.MANUAL_TOKEN_NOTIFICATION_BUFFER_SECONDS
        ):
            return
        if self._notify_expiry is None:
            return
        title = (
            "StreamVault Twitch OAuth token expired"
            if expired
            else "StreamVault Twitch OAuth token expires soon"
        )
        body = (
            "Your stored Twitch OAuth token has expired. Open Settings > Twitch Connection "
            "and save a fresh browser token to keep H.265/1440p recordings working."
            if expired
            else "Your stored Twitch OAuth token expires soon. Open Settings > Twitch Connection "
            "and save a fresh browser token to avoid recording quality fallback."
        )
        try:
            await self._notify_expiry(body, title)
            self._last_expiry_notification_at = now
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Could not send Twitch token expiry notification")

    async def validate_token(self, access_token: str) -> dict[str, object] | None:
        return await self._operation(
            "validate-token", self._validate_token(access_token)
        )

    async def _validate_token(self, access_token: str) -> dict[str, object] | None:
        try:
            reply = await self.http_client.request(
                "GET",
                self.VALIDATE_URL,
                headers={"Authorization": f"OAuth {access_token}"},
            )
            if reply.status_code != 200:
                return None
            payload = json.loads(reply.body)
            if isinstance(payload, dict):
                return {
                    key: value for key, value in payload.items() if isinstance(key, str)
                }
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Could not validate Twitch credentials")
        return None

    async def clear_tokens(self) -> bool:
        return await self._operation("clear-tokens", self._clear_tokens())

    async def _clear_tokens(self) -> bool:
        def clear(db: Session) -> bool:
            try:
                row = db.query(GlobalSettings).first()
                if row is not None:
                    row.twitch_refresh_token = None
                    row.twitch_access_token = None
                    row.twitch_token_expires_at = None
                    db.commit()
                return True
            except Exception:
                db.rollback()
                logger.error("Could not clear Twitch credentials")
                return False

        success = await self._in_db(clear)
        if success:
            self.settings.TWITCH_OAUTH_TOKEN = None
        return success
