"""Optional real-PostgreSQL regression coverage for Twitch upstream leases.

The test is opt-in so the normal suite remains hermetic. CI or local callers set
``STREAMVAULT_POSTGRES_TEST_URL`` to an isolated disposable PostgreSQL database.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    GlobalSettings,
    Recording,
    Stream,
    Streamer,
    TwitchUpstreamCoordinationState,
    TwitchUpstreamLease,
    User,
)
from app.services.twitch_upstream_coordinator import (
    AUTHENTICATED_TWITCH_ACCOUNT,
    TwitchUpstreamConflict,
    TwitchUpstreamCoordinator,
)


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)

    def utcnow(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return 1.0

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class _DeadProcessInspector:
    def is_exact_process_alive(self, **_identity) -> bool:
        return False


@pytest.fixture
def postgres_coordinator():
    url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")

    engine = create_engine(url, future=True)
    tables = [
        User.__table__,
        Streamer.__table__,
        Stream.__table__,
        Recording.__table__,
        TwitchUpstreamCoordinationState.__table__,
        TwitchUpstreamLease.__table__,
        GlobalSettings.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    clock = _Clock()
    coordinator = TwitchUpstreamCoordinator(
        Session,
        utc_clock=clock.utcnow,
        monotonic_clock=clock.monotonic,
        process_inspector=_DeadProcessInspector(),
    )
    try:
        yield Session, clock, coordinator
    finally:
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


@pytest.mark.asyncio
async def test_postgres_fresh_guard_serializes_distinct_channels(
    postgres_coordinator,
) -> None:
    """A fresh guard must not turn independent first leases into conflicts."""
    Session, _clock, coordinator = postgres_coordinator
    with Session() as db:
        db.add(GlobalSettings(id=1, twitch_max_concurrent_upstreams=12))
        db.commit()

    reservations = await asyncio.gather(
        *(
            coordinator.reserve(
                channel_key=f"postgres-bootstrap-{index}",
                auth_key=None,
                purpose="RECORDING",
            )
            for index in range(12)
        )
    )

    assert {reservation.channel_key for reservation in reservations} == {
        f"postgres-bootstrap-{index}" for index in range(12)
    }
    with Session() as db:
        assert db.query(TwitchUpstreamCoordinationState).count() == 1
        assert db.query(TwitchUpstreamLease).count() == 12


@pytest.mark.asyncio
async def test_postgres_lease_contention_renewal_expiry_and_takeover(
    postgres_coordinator,
) -> None:
    Session, clock, coordinator = postgres_coordinator
    release = asyncio.Event()
    ready = asyncio.Event()
    waiting = 0

    async def contender(index: int):
        nonlocal waiting
        waiting += 1
        if waiting == 12:
            ready.set()
        await release.wait()
        try:
            return await coordinator.reserve(
                channel_key="postgres-channel",
                auth_key=None,
                purpose="RECORDING",
            )
        except TwitchUpstreamConflict as conflict:
            return conflict.code

    tasks = [asyncio.create_task(contender(index)) for index in range(12)]
    await ready.wait()
    release.set()
    results = await asyncio.gather(*tasks)

    winners = [result for result in results if not isinstance(result, str)]
    assert len(winners) == 1
    winner = winners[0]
    assert results.count("twitch_upstream_channel_conflict") == 11

    assert await coordinator.heartbeat(
        channel_key=winner.channel_key, generation=winner.generation
    )
    clock.advance(31)
    assert await coordinator.reconcile() == 1

    takeover = await coordinator.reserve(
        channel_key=winner.channel_key,
        auth_key=None,
        purpose="RECOVERY",
        recording_id=winner.recording_id,
        expected_generation=winner.generation,
    )
    assert takeover.generation == winner.generation + 1
    assert takeover.state == "RECOVERING"
    with Session() as db:
        lease = db.query(TwitchUpstreamLease).one()
        assert db.query(TwitchUpstreamCoordinationState).count() == 1
        assert (lease.generation, lease.state) == (
            takeover.generation,
            "RECOVERING",
        )


@pytest.mark.asyncio
async def test_postgres_priority_is_dormant_across_real_coordinator_transitions(
    postgres_coordinator,
) -> None:
    """Exercise arbitration, rotation, capacity, and fencing on PostgreSQL."""
    Session, clock, coordinator = postgres_coordinator
    with Session() as db:
        db.add(GlobalSettings(id=1, twitch_max_concurrent_upstreams=3))
        db.commit()

    owner = await coordinator.reserve(
        channel_key="postgres-auth-owner",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
        purpose="RECORDING",
        auth_priority=-1000,
        anonymous_available=True,
        prefer_authenticated=True,
    )
    owner = await coordinator.activate(
        channel_key=owner.channel_key,
        generation=owner.generation,
        process_pid=1001,
        process_group_id=1001,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="postgres-owner-birth",
    )

    waiters = []
    for index, (channel_key, priority) in enumerate((
        ("postgres-older-waiter", -1000),
        ("postgres-newer-high-waiter", 1000),
    ), start=2):
        clock.advance(1)
        waiter = await coordinator.reserve(
            channel_key=channel_key,
            auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
            purpose="RECORDING",
            auth_priority=priority,
            anonymous_available=True,
            prefer_authenticated=True,
        )
        assert waiter.auth_key is None
        assert waiter.handoff_reason == "authenticated_owner_stable"
        waiter = await coordinator.activate(
            channel_key=waiter.channel_key,
            generation=waiter.generation,
            process_pid=1000 + index,
            process_group_id=1000 + index,
            process_started_at=clock.utcnow(),
            process_start_fingerprint=f"postgres-waiter-{index}-birth",
        )
        waiters.append(waiter)

    older, newer = waiters
    updated = await coordinator.update_auth_priority(
        channel_key=newer.channel_key,
        generation=newer.generation,
        priority=1000,
    )
    assert updated.handoff_reason == "authenticated_owner_stable"

    with Session() as db:
        persisted_owner = (
            db.query(TwitchUpstreamLease)
            .filter_by(channel_key=owner.channel_key)
            .one()
        )
        persisted_owner.handoff_target_channel = newer.channel_key
        persisted_owner.handoff_reason = "higher_priority_recording"
        persisted_owner.handoff_requested_at = clock.utcnow()
        db.commit()

    with pytest.raises(LookupError, match="no authentication transition"):
        await coordinator.begin_auth_transition(
            channel_key=owner.channel_key,
            generation=owner.generation,
        )

    with pytest.raises(TwitchUpstreamConflict) as capacity:
        await coordinator.reserve(
            channel_key="postgres-over-capacity",
            auth_key=None,
            purpose="LIVE",
            owner_user_id=8,
            live_session_id="postgres-over-capacity",
        )
    assert capacity.value.code == "twitch_upstream_total_budget_exhausted"

    rotating = await coordinator.begin_rotation(
        channel_key=owner.channel_key,
        generation=owner.generation,
    )
    assert rotating.state == "ROTATING"
    rotated = await coordinator.handoff_rotation(
        channel_key=owner.channel_key,
        generation=rotating.generation,
        process_pid=1004,
        process_group_id=1004,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="postgres-owner-rotated-birth",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
    )
    assert rotated.state == "ACTIVE"
    assert rotated.auth_key == AUTHENTICATED_TWITCH_ACCOUNT
    assert not await coordinator.heartbeat(
        channel_key=owner.channel_key,
        generation=owner.generation,
    )

    assert await coordinator.release(
        channel_key=rotated.channel_key,
        generation=rotated.generation,
        reason="postgres-owner-completed",
    )
    with pytest.raises(LookupError, match="oldest requester"):
        await coordinator.begin_auth_transition(
            channel_key=newer.channel_key,
            generation=newer.generation,
        )

    promotion = await coordinator.begin_auth_transition(
        channel_key=older.channel_key,
        generation=older.generation,
    )
    assert promotion.action == "promote"
    promoted = await coordinator.handoff_rotation(
        channel_key=older.channel_key,
        generation=promotion.reservation.generation,
        process_pid=1002,
        process_group_id=1002,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="postgres-older-promoted-birth",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
    )
    assert promoted.auth_key == AUTHENTICATED_TWITCH_ACCOUNT
    assert promoted.auth_requested is False
    with Session() as db:
        persisted_newer = (
            db.query(TwitchUpstreamLease)
            .filter_by(channel_key=newer.channel_key)
            .one()
        )
        assert persisted_newer.state == "ACTIVE"
        assert persisted_newer.auth_key is None
        assert persisted_newer.auth_priority == 1000
