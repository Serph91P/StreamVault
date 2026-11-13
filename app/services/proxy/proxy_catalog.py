"""Worker-local proxy catalogue transactions and immutable async handoffs."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, TypedDict

from sqlalchemy.orm import Session

from app.models import ProxySettings, RecordingSettings
from app.utils.security import sanitize_proxy_url_for_logging
from app.utils.proxy_encryption import get_proxy_encryption


class HealthResult(TypedDict):
    status: Literal["healthy", "degraded", "failed"]
    response_time_ms: int | None
    error: str | None


class ProxyPayload(TypedDict):
    id: int
    proxy_url: str
    masked_url: str
    priority: int
    enabled: bool
    last_check: str | None
    health_status: str
    response_time_ms: int | None
    consecutive_failures: int
    last_error: None
    total_requests: int
    successful_requests: int
    failed_requests: int
    created_at: str | None


@dataclass(frozen=True)
class ProxySnapshot:
    id: int
    url: str = field(repr=False)
    ciphertext: str = field(repr=False)
    priority: int
    enabled: bool
    last_check: str | None
    health_status: str
    response_time_ms: int | None
    consecutive_failures: int
    total_recordings: int
    failed_recordings: int
    created_at: str | None

    @classmethod
    def from_row(cls, row: ProxySettings) -> "ProxySnapshot":
        return cls(
            row.id,
            row.proxy_url,
            row._proxy_url_encrypted,
            row.priority,
            row.enabled,
            row.last_health_check.isoformat() if row.last_health_check else None,
            row.health_status,
            row.average_response_time_ms,
            row.consecutive_failures,
            row.total_recordings,
            row.failed_recordings,
            row.created_at.isoformat() if row.created_at else None,
        )

    def payload(self) -> ProxyPayload:
        safe_url = sanitize_proxy_url_for_logging(self.url)
        return {
            "id": self.id,
            "proxy_url": safe_url,
            "masked_url": safe_url,
            "priority": self.priority,
            "enabled": self.enabled,
            "last_check": self.last_check,
            "health_status": self.health_status,
            "response_time_ms": self.response_time_ms,
            "consecutive_failures": self.consecutive_failures,
            "last_error": None,
            "total_requests": self.total_recordings,
            "successful_requests": self.total_recordings - self.failed_recordings,
            "failed_requests": self.failed_recordings,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class ProxyPolicy:
    interval_seconds: int = 300
    enabled: bool = True
    max_failures: int = 3


def read_policy(factory: Callable[[], Session]) -> ProxyPolicy:
    with factory() as session:
        row = session.query(RecordingSettings).first()
        if row is None:
            return ProxyPolicy()
        return ProxyPolicy(
            row.proxy_health_check_interval_seconds
            if row.proxy_health_check_interval_seconds is not None
            else 300,
            bool(row.proxy_health_check_enabled),
            row.proxy_max_consecutive_failures
            if row.proxy_max_consecutive_failures is not None
            else 3,
        )


def read_targets(factory: Callable[[], Session]) -> list[ProxySnapshot]:
    with factory() as session:
        rows = (
            session.query(ProxySettings).filter(ProxySettings.enabled.is_(True)).all()
        )
        if rows:
            get_proxy_encryption(session)
        return [ProxySnapshot.from_row(row) for row in rows]


def read_target(factory: Callable[[], Session], proxy_id: int) -> ProxySnapshot | None:
    with factory() as session:
        row = session.get(ProxySettings, proxy_id)
        if row is not None:
            get_proxy_encryption(session)
        return ProxySnapshot.from_row(row) if row else None


def apply_health(
    factory: Callable[[], Session],
    target: ProxySnapshot,
    result: HealthResult,
    *,
    max_failures: int | None,
) -> tuple[ProxySnapshot, bool] | None:
    with factory() as session:
        row = (
            session.query(ProxySettings)
            .filter(ProxySettings.id == target.id)
            .with_for_update()
            .first()
        )
        if row is None or row._proxy_url_encrypted != target.ciphertext:
            return None
        get_proxy_encryption(session)
        row.last_health_check = datetime.now(timezone.utc)
        row.health_status = result["status"]
        row.average_response_time_ms = result["response_time_ms"]
        row.consecutive_failures = (
            row.consecutive_failures + 1 if result["status"] == "failed" else 0
        )
        disabled = (
            max_failures is not None
            and row.enabled
            and row.consecutive_failures >= max_failures
        )
        if disabled:
            row.enabled = False
        session.commit()
        return ProxySnapshot.from_row(row), disabled


def increment_stats(
    factory: Callable[[], Session], proxy_url: str, success: bool
) -> None:
    with factory() as session:
        rows = session.query(ProxySettings).with_for_update().all()
        if rows:
            get_proxy_encryption(session)
        for row in rows:
            if row.proxy_url == proxy_url:
                row.total_recordings += 1
                if not success:
                    row.failed_recordings += 1
                row.update_success_rate()
                session.commit()
                return
