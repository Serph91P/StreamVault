"""Post-migration bootstrap for persistent application security identities."""

from __future__ import annotations

import base64
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select, text

from app.models import SystemConfig

_BOOTSTRAP_LOCK_ID = 7_314_908_421
_EVENTSUB_KEY = "eventsub_secret"
_VAPID_PUBLIC_KEY = "vapid_public_key"
_VAPID_PRIVATE_KEY = "vapid_private_key"
_VAPID_CLAIMS_SUB = "vapid_claims_sub"


class PersistentKeyBootstrapError(RuntimeError):
    """Raised when persistent identities cannot be loaded or stored atomically."""


@dataclass(frozen=True)
class PersistentKeyMaterial:
    eventsub_secret: str = field(repr=False)
    vapid_public_key: str
    vapid_private_key: str = field(repr=False)
    vapid_claims_sub: str


def generate_vapid_keys() -> tuple[str, str]:
    """Generate one P-256 VAPID identity without logging key material."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_key_der = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return (
        base64.urlsafe_b64encode(public_key).decode("ascii").rstrip("="),
        base64.b64encode(private_key_der).decode("ascii"),
    )


class PersistentKeyBootstrapService:
    """Load or atomically create EventSub and VAPID identities after migrations."""

    def __init__(
        self,
        session_factory: Callable[[], Any],
        *,
        vapid_key_generator: Callable[
            [], tuple[str | None, str | None]
        ] = generate_vapid_keys,
        eventsub_secret_generator: Callable[[], str] = lambda: secrets.token_urlsafe(
            32
        ),
    ) -> None:
        self._session_factory = session_factory
        self._vapid_key_generator = vapid_key_generator
        self._eventsub_secret_generator = eventsub_secret_generator

    def bootstrap(self, settings: Any) -> PersistentKeyMaterial:
        configured_eventsub = settings.EVENTSUB_SECRET
        configured_vapid_public = settings.VAPID_PUBLIC_KEY
        configured_vapid_private = settings.VAPID_PRIVATE_KEY
        claims_sub = settings.VAPID_CLAIMS_SUB

        if configured_eventsub and configured_vapid_public and configured_vapid_private:
            return PersistentKeyMaterial(
                eventsub_secret=configured_eventsub,
                vapid_public_key=configured_vapid_public,
                vapid_private_key=configured_vapid_private,
                vapid_claims_sub=claims_sub,
            )

        try:
            with self._session_factory() as session, session.begin():
                if session.get_bind().dialect.name == "postgresql":
                    session.execute(
                        text("SELECT pg_advisory_xact_lock(:lock_id)"),
                        {"lock_id": _BOOTSTRAP_LOCK_ID},
                    )

                required_keys = {
                    _EVENTSUB_KEY,
                    _VAPID_PUBLIC_KEY,
                    _VAPID_PRIVATE_KEY,
                    _VAPID_CLAIMS_SUB,
                }
                rows = session.scalars(
                    select(SystemConfig).where(SystemConfig.key.in_(required_keys))
                ).all()
                stored = {row.key: row for row in rows}

                eventsub_secret = configured_eventsub or self._stored_value(
                    stored, _EVENTSUB_KEY
                )
                if not eventsub_secret:
                    eventsub_secret = self._eventsub_secret_generator()
                    if not eventsub_secret:
                        raise PersistentKeyBootstrapError(
                            "EventSub secret generation returned no key material"
                        )
                    self._upsert(
                        session,
                        stored,
                        _EVENTSUB_KEY,
                        eventsub_secret,
                        "Persistent EventSub webhook signing secret",
                    )

                vapid_public = configured_vapid_public
                vapid_private = configured_vapid_private
                if not (vapid_public and vapid_private):
                    stored_public = self._stored_value(stored, _VAPID_PUBLIC_KEY)
                    stored_private = self._stored_value(stored, _VAPID_PRIVATE_KEY)
                    if stored_public and stored_private:
                        vapid_public, vapid_private = stored_public, stored_private
                        stored_claims = self._stored_value(stored, _VAPID_CLAIMS_SUB)
                        if stored_claims:
                            claims_sub = stored_claims
                    else:
                        vapid_public, vapid_private = self._vapid_key_generator()
                        if not vapid_public or not vapid_private:
                            raise PersistentKeyBootstrapError(
                                "VAPID generation returned incomplete key material"
                            )
                        self._upsert(
                            session,
                            stored,
                            _VAPID_PUBLIC_KEY,
                            vapid_public,
                            "VAPID public key for push notifications",
                        )
                        self._upsert(
                            session,
                            stored,
                            _VAPID_PRIVATE_KEY,
                            vapid_private,
                            "VAPID private key for push notifications",
                        )
                        self._upsert(
                            session,
                            stored,
                            _VAPID_CLAIMS_SUB,
                            claims_sub,
                            "VAPID claims subject for push notifications",
                        )

                material = PersistentKeyMaterial(
                    eventsub_secret=eventsub_secret,
                    vapid_public_key=vapid_public,
                    vapid_private_key=vapid_private,
                    vapid_claims_sub=claims_sub,
                )
        except PersistentKeyBootstrapError:
            raise
        except Exception as error:
            raise PersistentKeyBootstrapError(
                "Persistent key bootstrap failed; startup cannot continue"
            ) from error

        settings.apply_persistent_keys(
            eventsub_secret=material.eventsub_secret,
            vapid_public_key=material.vapid_public_key,
            vapid_private_key=material.vapid_private_key,
        )
        return material

    @staticmethod
    def _stored_value(stored: dict[str, SystemConfig], key: str) -> str | None:
        row = stored.get(key)
        return row.value if row else None

    @staticmethod
    def _upsert(
        session: Any,
        stored: dict[str, SystemConfig],
        key: str,
        value: str,
        description: str,
    ) -> None:
        row = stored.get(key)
        if row is None:
            row = SystemConfig(key=key, value=value, description=description)
            stored[key] = row
            session.add(row)
        else:
            row.value = value
            row.description = description


def bootstrap_persistent_keys() -> PersistentKeyMaterial:
    """Bootstrap the process settings using the post-migration DB session seam."""
    from app.config.settings import settings
    from app.database import SessionLocal

    return PersistentKeyBootstrapService(SessionLocal).bootstrap(settings)
