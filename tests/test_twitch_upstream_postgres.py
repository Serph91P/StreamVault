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
