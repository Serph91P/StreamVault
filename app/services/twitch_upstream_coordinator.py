import asyncio
import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import psutil
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    GlobalSettings,
    TwitchUpstreamCoordinationState,
    TwitchUpstreamLease,
)

AUTHENTICATED_TWITCH_ACCOUNT = "streamvault-global-twitch-account"
ACTIVE_STATES = ("STARTING", "ACTIVE", "ROTATING", "RECOVERING")
PURPOSES = ("RECORDING", "LIVE", "ROTATION", "RECOVERY")


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    process_group_id: int
    started_at: datetime
    fingerprint: str


@dataclass(frozen=True)
class TwitchUpstreamReservation:
    channel_key: str
    auth_key: Optional[str]
    owner_user_id: Optional[int]
    recording_id: Optional[int]
    live_session_id: Optional[str]
    purpose: str
    state: str
    generation: int
    process_pid: Optional[int] = None
    process_group_id: Optional[int] = None
    process_started_at: Optional[datetime] = None
    process_start_fingerprint: Optional[str] = None


class TwitchUpstreamConflict(RuntimeError):
    def __init__(self, code: str, reason: str, channel_key: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
        self.channel_key = channel_key

    def as_detail(self) -> dict:
        return {
            "code": self.code,
            "reason": self.reason,
            "channel_key": self.channel_key,
            "retryable": False,
        }


class ProcessInspector:
    def inspect(self, pid: int) -> ProcessIdentity:
        process = psutil.Process(pid)
        started_at = datetime.fromtimestamp(process.create_time(), tz=timezone.utc)
        fingerprint = hashlib.sha256(
            f"{pid}:{process.create_time()}".encode("ascii")
        ).hexdigest()
        return ProcessIdentity(
            pid=pid,
            process_group_id=os.getpgid(pid),
            started_at=started_at,
            fingerprint=fingerprint,
        )

    def is_exact_process_alive(self, **identity) -> bool:
        pid = identity.get("process_pid")
        process_group_id = identity.get("process_group_id")
        fingerprint = identity.get("process_start_fingerprint")
        if pid is None or process_group_id is None or not fingerprint:
            return False
        try:
            current = self.inspect(pid)
            return (
                current.pid,
                current.process_group_id,
                current.fingerprint,
            ) == (pid, process_group_id, fingerprint)
        except (OSError, psutil.Error):
            return False


class TwitchUpstreamCoordinator:
    def __init__(
        self,
        session_factory,
        *,
        utc_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic_clock: Callable[[], float],
        process_inspector=None,
        lease_ttl_seconds: int = 30,
        authenticated_budget: int = 1,
    ) -> None:
        self._session_factory = session_factory
        self._utcnow = utc_clock
        self._monotonic = monotonic_clock
        self._process_inspector = process_inspector or ProcessInspector()
        self._lease_ttl = timedelta(seconds=lease_ttl_seconds)
        self._authenticated_budget = authenticated_budget

    async def reserve(
        self,
        *,
        channel_key: str,
        auth_key: Optional[str],
        purpose: str,
        owner_user_id: Optional[int] = None,
        recording_id: Optional[int] = None,
        live_session_id: Optional[str] = None,
        expected_generation: Optional[int] = None,
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._reserve,
            channel_key,
            auth_key,
            purpose,
            owner_user_id,
            recording_id,
            live_session_id,
            expected_generation,
        )

    async def activate(
        self,
        *,
        channel_key: str,
        generation: int,
        process_pid: int,
        process_group_id: Optional[int] = None,
        process_started_at: Optional[datetime] = None,
        process_start_fingerprint: Optional[str] = None,
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._activate,
            channel_key,
            generation,
            process_pid,
            process_group_id,
            process_started_at,
            process_start_fingerprint,
        )

    async def heartbeat(self, *, channel_key: str, generation: int) -> bool:
        return await asyncio.to_thread(self._heartbeat, channel_key, generation)

    async def begin_rotation(
        self, *, channel_key: str, generation: int
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(self._begin_rotation, channel_key, generation)

    async def handoff_rotation(
        self,
        *,
        channel_key: str,
        generation: int,
        process_pid: int,
        process_group_id: Optional[int] = None,
        process_started_at: Optional[datetime] = None,
        process_start_fingerprint: Optional[str] = None,
        purpose: str = "RECORDING",
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._handoff_rotation,
            channel_key,
            generation,
            process_pid,
            process_group_id,
            process_started_at,
            process_start_fingerprint,
            purpose,
        )

    async def release(
        self,
        *,
        channel_key: str,
        generation: int,
        reason: str,
    ) -> bool:
        return await asyncio.to_thread(
            self._release, channel_key, generation, reason[:64]
        )

    async def reconcile(self, *, batch_size: int = 100) -> int:
        return await asyncio.to_thread(self._reconcile, batch_size)

    async def inspect_process_identity(self, process_pid: int) -> ProcessIdentity:
        return await asyncio.to_thread(self._process_inspector.inspect, process_pid)

    async def assert_stop_authorized(
        self,
        *,
        channel_key: str,
        generation: int,
        process_pid: int,
        process_group_id: int,
        process_start_fingerprint: str,
        expected_purpose: Optional[str] = None,
        requesting_owner_user_id: Optional[int] = None,
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._assert_stop_authorized,
            channel_key,
            generation,
            process_pid,
            process_group_id,
            process_start_fingerprint,
            expected_purpose,
            requesting_owner_user_id,
        )

    async def assert_exited_process_cleanup_authorized(
        self,
        *,
        channel_key: str,
        generation: int,
        process_pid: int,
        process_group_id: int,
        process_start_fingerprint: str,
        expected_purpose: str,
        requesting_owner_user_id: Optional[int],
        expected_live_session_id: str,
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._assert_exited_process_cleanup_authorized,
            channel_key,
            generation,
            process_pid,
            process_group_id,
            process_start_fingerprint,
            expected_purpose,
            requesting_owner_user_id,
            expected_live_session_id,
        )

    async def assert_rotation_replacement_cleanup_authorized(
        self,
        *,
        channel_key: str,
        generation: int,
        process_pid: int,
        process_group_id: int,
        process_start_fingerprint: str,
    ) -> TwitchUpstreamReservation:
        return await asyncio.to_thread(
            self._assert_rotation_replacement_cleanup_authorized,
            channel_key,
            generation,
            process_pid,
            process_group_id,
            process_start_fingerprint,
        )

    def _reserve(
        self,
        channel_key,
        auth_key,
        purpose,
        owner_user_id,
        recording_id,
        live_session_id,
        expected_generation,
    ):
        if not channel_key or len(channel_key) > 255:
            raise ValueError("channel_key must be a non-empty Twitch channel ID")
        if purpose not in PURPOSES:
            raise ValueError(f"Unsupported upstream purpose: {purpose}")
        if purpose == "ROTATION":
            raise ValueError("ROTATION must use begin_rotation")
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            self._reconcile_expired(db, now, 100)
            existing = db.execute(
                select(TwitchUpstreamLease).where(
                    TwitchUpstreamLease.channel_key == channel_key
                )
            ).scalar_one_or_none()

            if existing and existing.state in ACTIVE_STATES:
                if (
                    existing.state == "ACTIVE"
                    and existing.purpose == "LIVE"
                    and purpose == "LIVE"
                    and existing.owner_user_id == owner_user_id
                    and existing.auth_key == auth_key
                ):
                    db.commit()
                    return self._snapshot(existing)
                if (
                    existing.purpose == "LIVE"
                    and purpose == "LIVE"
                    and existing.owner_user_id == owner_user_id
                    and existing.auth_key != auth_key
                ):
                    self._conflict(
                        "twitch_upstream_live_policy_conflict",
                        "live_policy_mismatch",
                        channel_key,
                    )
                self._conflict(
                    "twitch_upstream_channel_conflict",
                    "channel_already_reserved",
                    channel_key,
                )

            if purpose == "RECOVERY":
                if not existing or expected_generation != existing.generation:
                    self._conflict(
                        "twitch_upstream_channel_conflict",
                        "recovery_generation_mismatch",
                        channel_key,
                    )
                expired = db.execute(
                    select(TwitchUpstreamLease.id).where(
                        TwitchUpstreamLease.id == existing.id,
                        TwitchUpstreamLease.expires_at < now,
                    )
                ).scalar_one_or_none()
                identity = {
                    "process_pid": existing.process_pid,
                    "process_group_id": existing.process_group_id,
                    "process_started_at": existing.process_started_at,
                    "process_start_fingerprint": existing.process_start_fingerprint,
                }
                if (
                    existing.state != "RELEASED"
                    or existing.release_reason != "reconciled_stale_process"
                    or expired is None
                    or self._process_inspector.is_exact_process_alive(**identity)
                ):
                    self._conflict(
                        "twitch_upstream_channel_conflict",
                        "recovery_precondition_failed",
                        channel_key,
                    )

            active_count = (
                db.query(TwitchUpstreamLease)
                .filter(TwitchUpstreamLease.state.in_(ACTIVE_STATES))
                .count()
            )
            if auth_key is not None:
                authenticated_count = (
                    db.query(TwitchUpstreamLease)
                    .filter(
                        TwitchUpstreamLease.auth_key.is_not(None),
                        TwitchUpstreamLease.state.in_(ACTIVE_STATES),
                    )
                    .count()
                )
                if authenticated_count >= self._authenticated_budget:
                    self._conflict(
                        "twitch_upstream_authenticated_budget_exhausted",
                        "authenticated_budget_exhausted",
                        channel_key,
                    )

            settings = db.query(GlobalSettings).first()
            total_budget = settings.twitch_max_concurrent_upstreams if settings else 5
            if active_count >= total_budget:
                self._conflict(
                    "twitch_upstream_total_budget_exhausted",
                    "total_budget_exhausted",
                    channel_key,
                )

            generation = existing.generation + 1 if existing else 1
            state = "RECOVERING" if purpose == "RECOVERY" else "STARTING"
            if existing:
                lease = existing
                lease.auth_key = auth_key
                lease.owner_user_id = owner_user_id
                lease.recording_id = recording_id
                lease.live_session_id = live_session_id
                lease.purpose = purpose
                lease.state = state
                lease.generation = generation
            else:
                lease = TwitchUpstreamLease(
                    channel_key=channel_key,
                    created_at=now,
                )
                db.add(lease)
                lease.auth_key = auth_key
                lease.owner_user_id = owner_user_id
                lease.recording_id = recording_id
                lease.live_session_id = live_session_id
                lease.purpose = purpose
                lease.state = state
                lease.generation = generation
            lease.process_pid = None
            lease.process_group_id = None
            lease.process_started_at = None
            lease.process_start_fingerprint = None
            lease.reserved_at = now
            lease.activated_at = None
            lease.heartbeat_at = now
            lease.expires_at = now + self._lease_ttl
            lease.released_at = None
            lease.release_reason = None
            lease.updated_at = now
            db.flush()
            result = self._snapshot(lease)
            db.commit()
            return result
        except TwitchUpstreamConflict:
            db.rollback()
            raise
        except IntegrityError:
            db.rollback()
            self._conflict(
                "twitch_upstream_channel_conflict",
                "channel_already_reserved",
                channel_key,
            )
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _activate(
        self,
        channel_key,
        generation,
        process_pid,
        process_group_id,
        process_started_at,
        process_start_fingerprint,
    ):
        identity = self._resolve_identity(
            process_pid,
            process_group_id,
            process_started_at,
            process_start_fingerprint,
        )
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            lease = self._lease_for_generation(db, channel_key, generation)
            if lease.state not in ("STARTING", "RECOVERING"):
                raise PermissionError("lease is not awaiting activation")
            self._set_active_identity(lease, identity, now)
            db.commit()
            return self._snapshot(lease)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _heartbeat(self, channel_key, generation):
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            lease = self._lease_for_generation(db, channel_key, generation)
            if lease.state not in ACTIVE_STATES:
                return False
            lease.heartbeat_at = now
            lease.expires_at = now + self._lease_ttl
            lease.updated_at = now
            db.commit()
            return True
        except (LookupError, PermissionError):
            db.rollback()
            return False
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _begin_rotation(self, channel_key, generation):
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            lease = self._lease_for_generation(db, channel_key, generation)
            if lease.state != "ACTIVE":
                raise PermissionError("only an active lease may rotate")
            lease.generation += 1
            lease.purpose = "ROTATION"
            lease.state = "ROTATING"
            lease.heartbeat_at = now
            lease.expires_at = now + self._lease_ttl
            lease.updated_at = now
            db.commit()
            return self._snapshot(lease)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _handoff_rotation(
        self,
        channel_key,
        generation,
        process_pid,
        process_group_id,
        process_started_at,
        process_start_fingerprint,
        purpose,
    ):
        if purpose not in ("RECORDING", "LIVE"):
            raise ValueError("rotation handoff purpose must be RECORDING or LIVE")
        identity = self._resolve_identity(
            process_pid,
            process_group_id,
            process_started_at,
            process_start_fingerprint,
        )
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            lease = self._lease_for_generation(db, channel_key, generation)
            if lease.state != "ROTATING":
                raise PermissionError("lease is not rotating")
            lease.purpose = purpose
            self._set_active_identity(lease, identity, now)
            db.commit()
            return self._snapshot(lease)
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _release(self, channel_key, generation, reason):
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            lease = db.execute(
                select(TwitchUpstreamLease).where(
                    TwitchUpstreamLease.channel_key == channel_key,
                    TwitchUpstreamLease.generation == generation,
                    TwitchUpstreamLease.state.in_(ACTIVE_STATES),
                )
            ).scalar_one_or_none()
            if not lease:
                db.rollback()
                return False
            self._mark_released(lease, now, reason)
            db.commit()
            return True
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _reconcile(self, batch_size):
        now = self._utcnow()
        db = self._session_factory()
        try:
            self._begin_guarded_transaction(db)
            self._lock_guard(db, now)
            released = self._reconcile_expired(db, now, batch_size)
            db.commit()
            return released
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _assert_stop_authorized(
        self,
        channel_key,
        generation,
        process_pid,
        process_group_id,
        process_start_fingerprint,
        expected_purpose,
        requesting_owner_user_id,
    ):
        with self._session_factory() as db:
            lease = self._lease_for_generation(db, channel_key, generation)
            identity = {
                "process_pid": lease.process_pid,
                "process_group_id": lease.process_group_id,
                "process_started_at": lease.process_started_at,
                "process_start_fingerprint": lease.process_start_fingerprint,
            }
            if (
                lease.state not in ACTIVE_STATES
                or (
                    lease.process_pid,
                    lease.process_group_id,
                    lease.process_start_fingerprint,
                )
                != (process_pid, process_group_id, process_start_fingerprint)
                or (
                    expected_purpose is not None
                    and (
                        lease.purpose != expected_purpose
                        or lease.owner_user_id != requesting_owner_user_id
                    )
                )
                or not self._process_inspector.is_exact_process_alive(**identity)
            ):
                raise PermissionError("stale or foreign process owner")
            return self._snapshot(lease)

    def _assert_exited_process_cleanup_authorized(
        self,
        channel_key,
        generation,
        process_pid,
        process_group_id,
        process_start_fingerprint,
        expected_purpose,
        requesting_owner_user_id,
        expected_live_session_id,
    ):
        with self._session_factory() as db:
            lease = self._lease_for_generation(db, channel_key, generation)
            identity = {
                "process_pid": lease.process_pid,
                "process_group_id": lease.process_group_id,
                "process_started_at": lease.process_started_at,
                "process_start_fingerprint": lease.process_start_fingerprint,
            }
            if (
                lease.state not in ACTIVE_STATES
                or (
                    lease.process_pid,
                    lease.process_group_id,
                    lease.process_start_fingerprint,
                )
                != (process_pid, process_group_id, process_start_fingerprint)
                or lease.purpose != expected_purpose
                or lease.owner_user_id != requesting_owner_user_id
                or lease.live_session_id != expected_live_session_id
                or self._process_inspector.is_exact_process_alive(**identity)
            ):
                raise PermissionError("stale, live, or foreign process owner")
            return self._snapshot(lease)

    def _assert_rotation_replacement_cleanup_authorized(
        self,
        channel_key,
        generation,
        process_pid,
        process_group_id,
        process_start_fingerprint,
    ):
        with self._session_factory() as db:
            lease = self._lease_for_generation(db, channel_key, generation)
            replacement_identity = {
                "process_pid": process_pid,
                "process_group_id": process_group_id,
                "process_start_fingerprint": process_start_fingerprint,
            }
            if (
                lease.state != "ROTATING"
                or (
                    lease.process_pid,
                    lease.process_group_id,
                    lease.process_start_fingerprint,
                )
                == (process_pid, process_group_id, process_start_fingerprint)
                or not self._process_inspector.is_exact_process_alive(
                    **replacement_identity
                )
            ):
                raise PermissionError("stale or foreign rotation replacement")
            return self._snapshot(lease)

    def _begin_guarded_transaction(self, db):
        if db.get_bind().dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        else:
            db.begin()

    def _lock_guard(self, db, now):
        query = select(TwitchUpstreamCoordinationState).where(
            TwitchUpstreamCoordinationState.id == 1
        )
        if db.get_bind().dialect.name == "postgresql":
            query = query.with_for_update()
        guard = db.execute(query).scalar_one_or_none()
        if guard is None:
            guard = TwitchUpstreamCoordinationState(
                id=1, lock_version=0, updated_at=now
            )
            db.add(guard)
            db.flush()
        guard.lock_version += 1
        guard.updated_at = now

    def _reconcile_expired(self, db, now, batch_size):
        leases = db.execute(
            select(TwitchUpstreamLease)
            .where(
                TwitchUpstreamLease.state.in_(ACTIVE_STATES),
                TwitchUpstreamLease.expires_at < now,
            )
            .order_by(TwitchUpstreamLease.expires_at, TwitchUpstreamLease.id)
            .limit(batch_size)
        ).scalars()
        released = 0
        for lease in leases:
            identity = {
                "process_pid": lease.process_pid,
                "process_group_id": lease.process_group_id,
                "process_started_at": lease.process_started_at,
                "process_start_fingerprint": lease.process_start_fingerprint,
            }
            if not self._process_inspector.is_exact_process_alive(**identity):
                self._mark_released(lease, now, "reconciled_stale_process")
                released += 1
        return released

    def _resolve_identity(self, pid, group_id, started_at, fingerprint):
        if group_id is None or started_at is None or fingerprint is None:
            return self._process_inspector.inspect(pid)
        return ProcessIdentity(pid, group_id, started_at, fingerprint)

    def _set_active_identity(self, lease, identity, now):
        lease.state = "ACTIVE"
        lease.process_pid = identity.pid
        lease.process_group_id = identity.process_group_id
        lease.process_started_at = identity.started_at
        lease.process_start_fingerprint = identity.fingerprint
        lease.activated_at = now
        lease.heartbeat_at = now
        lease.expires_at = now + self._lease_ttl
        lease.updated_at = now

    @staticmethod
    def _lease_for_generation(db, channel_key, generation):
        lease = db.execute(
            select(TwitchUpstreamLease).where(
                TwitchUpstreamLease.channel_key == channel_key,
                TwitchUpstreamLease.generation == generation,
            )
        ).scalar_one_or_none()
        if lease is None:
            raise PermissionError("stale lease generation")
        return lease

    @staticmethod
    def _mark_released(lease, now, reason):
        lease.state = "RELEASED"
        lease.released_at = now
        lease.release_reason = reason[:64]
        lease.updated_at = now

    @staticmethod
    def _snapshot(lease):
        return TwitchUpstreamReservation(
            channel_key=lease.channel_key,
            auth_key=lease.auth_key,
            owner_user_id=lease.owner_user_id,
            recording_id=lease.recording_id,
            live_session_id=lease.live_session_id,
            purpose=lease.purpose,
            state=lease.state,
            generation=lease.generation,
            process_pid=lease.process_pid,
            process_group_id=lease.process_group_id,
            process_started_at=lease.process_started_at,
            process_start_fingerprint=lease.process_start_fingerprint,
        )

    @staticmethod
    def _conflict(code, reason, channel_key):
        raise TwitchUpstreamConflict(code, reason, channel_key)


from app.database import SessionLocal  # noqa: E402

twitch_upstream_coordinator = TwitchUpstreamCoordinator(
    SessionLocal,
    monotonic_clock=time.monotonic,
)
