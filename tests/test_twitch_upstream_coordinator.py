import asyncio
import socket
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    GlobalSettings,
    TwitchUpstreamCoordinationState,
    TwitchUpstreamLease,
)
from app.services.twitch_upstream_coordinator import (
    AUTHENTICATED_TWITCH_ACCOUNT,
    TwitchUpstreamConflict,
    TwitchUpstreamCoordinator,
)


@pytest.fixture(autouse=True)
def block_network_egress(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("coordinator tests must not use network egress")

    monkeypatch.setattr(socket, "create_connection", blocked)


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)

    def utcnow(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return 1.0

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class FakeProcessInspector:
    def __init__(self) -> None:
        self.alive_fingerprints = set()

    def is_exact_process_alive(self, **identity) -> bool:
        return identity.get("process_start_fingerprint") in self.alive_fingerprints


def make_coordinator(tmp_path, name="coordinator.db"):
    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        future=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            TwitchUpstreamCoordinationState.__table__,
            TwitchUpstreamLease.__table__,
            GlobalSettings.__table__,
        ],
    )
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    clock = FakeClock()
    inspector = FakeProcessInspector()
    coordinator = TwitchUpstreamCoordinator(
        Session,
        utc_clock=clock.utcnow,
        monotonic_clock=clock.monotonic,
        process_inspector=inspector,
    )
    return engine, Session, clock, inspector, coordinator


@pytest.mark.asyncio
async def test_concurrent_same_channel_reservations_have_one_winner(tmp_path) -> None:
    engine, Session, _clock, _inspector, coordinator = make_coordinator(tmp_path)
    ready = 0
    all_ready = asyncio.Event()
    release = asyncio.Event()

    async def contender(index: int):
        nonlocal ready
        ready += 1
        if ready == 24:
            all_ready.set()
        await release.wait()
        try:
            return await coordinator.reserve(
                channel_key="stable-twitch-id",
                auth_key=None,
                purpose="LIVE",
                owner_user_id=index + 1,
                live_session_id=f"session-{index}",
            )
        except TwitchUpstreamConflict as conflict:
            return conflict.code

    tasks = [asyncio.create_task(contender(index)) for index in range(24)]
    await all_ready.wait()
    release.set()
    results = await asyncio.gather(*tasks)

    winners = [result for result in results if not isinstance(result, str)]
    assert len(winners) == 1
    assert winners[0].channel_key == "stable-twitch-id"
    assert winners[0].generation == 1
    assert results.count("twitch_upstream_channel_conflict") == 23

    with Session() as db:
        leases = db.query(TwitchUpstreamLease).all()
        assert len(leases) == 1
        assert leases[0].state == "STARTING"
        assert leases[0].live_session_id == winners[0].live_session_id

    engine.dispose()


@pytest.mark.asyncio
async def test_generation_fencing_rotation_and_pid_reuse(tmp_path) -> None:
    engine, _Session, clock, inspector, coordinator = make_coordinator(tmp_path)
    started_at = clock.utcnow()
    reservation = await coordinator.reserve(
        channel_key="channel-1",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
        purpose="RECORDING",
        recording_id=9,
    )
    active = await coordinator.activate(
        channel_key=reservation.channel_key,
        generation=reservation.generation,
        process_pid=101,
        process_group_id=101,
        process_started_at=started_at,
        process_start_fingerprint="birth-101-a",
    )
    inspector.alive_fingerprints.add("birth-101-a")
    clock.advance(31)
    assert await coordinator.reconcile() == 0

    rotating = await coordinator.begin_rotation(
        channel_key=active.channel_key, generation=active.generation
    )
    assert rotating.state == "ROTATING"
    assert rotating.generation == 2
    await coordinator.assert_stop_authorized(
        channel_key=rotating.channel_key,
        generation=rotating.generation,
        process_pid=101,
        process_group_id=101,
        process_start_fingerprint="birth-101-a",
    )
    replacement = await coordinator.handoff_rotation(
        channel_key=rotating.channel_key,
        generation=rotating.generation,
        process_pid=101,
        process_group_id=101,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="birth-101-b",
    )
    assert replacement.state == "ACTIVE"
    assert replacement.purpose == "RECORDING"

    with pytest.raises(PermissionError):
        await coordinator.assert_stop_authorized(
            channel_key=active.channel_key,
            generation=active.generation,
            process_pid=101,
            process_group_id=101,
            process_start_fingerprint="birth-101-a",
        )
    assert not await coordinator.release(
        channel_key=active.channel_key,
        generation=active.generation,
        reason="stale_monitor",
    )

    # The PID was reused, but the exact birth fingerprint differs.
    inspector.alive_fingerprints = {"birth-101-a"}
    clock.advance(31)
    assert await coordinator.reconcile() == 1
    recovered = await coordinator.reserve(
        channel_key="channel-1",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
        purpose="RECOVERY",
        recording_id=9,
        expected_generation=replacement.generation,
    )
    assert recovered.state == "RECOVERING"
    assert recovered.generation == 3
    engine.dispose()


@pytest.mark.asyncio
async def test_idempotency_policy_and_global_budgets(tmp_path) -> None:
    engine, Session, clock, _inspector, coordinator = make_coordinator(
        tmp_path, "budgets.db"
    )
    with Session() as db:
        db.add(GlobalSettings(id=1, twitch_max_concurrent_upstreams=3))
        db.commit()

    live = await coordinator.reserve(
        channel_key="live-channel",
        auth_key=None,
        purpose="LIVE",
        owner_user_id=1,
        live_session_id="session-original",
    )
    live = await coordinator.activate(
        channel_key=live.channel_key,
        generation=live.generation,
        process_pid=201,
        process_group_id=201,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="birth-201",
    )
    duplicate = await coordinator.reserve(
        channel_key="live-channel",
        auth_key=None,
        purpose="LIVE",
        owner_user_id=1,
        live_session_id="session-new",
    )
    assert duplicate.live_session_id == "session-original"
    assert duplicate.generation == live.generation

    with pytest.raises(TwitchUpstreamConflict) as policy:
        await coordinator.reserve(
            channel_key="live-channel",
            auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
            purpose="LIVE",
            owner_user_id=1,
            live_session_id="enhanced",
        )
    assert policy.value.code == "twitch_upstream_live_policy_conflict"

    await coordinator.reserve(
        channel_key="anonymous-channel",
        auth_key=None,
        purpose="LIVE",
        owner_user_id=2,
        live_session_id="anonymous",
    )
    await coordinator.reserve(
        channel_key="authenticated-channel",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
        purpose="RECORDING",
        recording_id=10,
    )
    with pytest.raises(TwitchUpstreamConflict) as authenticated:
        await coordinator.reserve(
            channel_key="second-authenticated-channel",
            auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
            purpose="RECORDING",
            recording_id=11,
        )
    assert authenticated.value.code == "twitch_upstream_authenticated_budget_exhausted"
    with pytest.raises(TwitchUpstreamConflict) as total:
        await coordinator.reserve(
            channel_key="fourth-anonymous-channel",
            auth_key=None,
            purpose="LIVE",
            owner_user_id=3,
            live_session_id="fourth",
        )
    assert total.value.code == "twitch_upstream_total_budget_exhausted"
    engine.dispose()


@pytest.mark.asyncio
async def test_recording_and_live_collide_on_stable_channel(tmp_path) -> None:
    engine, _Session, _clock, _inspector, coordinator = make_coordinator(
        tmp_path, "mixed.db"
    )
    await coordinator.reserve(
        channel_key="stable-mixed-channel",
        auth_key=AUTHENTICATED_TWITCH_ACCOUNT,
        purpose="RECORDING",
        recording_id=22,
    )

    with pytest.raises(TwitchUpstreamConflict) as conflict:
        await coordinator.reserve(
            channel_key="stable-mixed-channel",
            auth_key=None,
            purpose="LIVE",
            owner_user_id=3,
            live_session_id="must-not-start",
        )

    assert conflict.value.as_detail() == {
        "code": "twitch_upstream_channel_conflict",
        "reason": "channel_already_reserved",
        "channel_key": "stable-mixed-channel",
        "retryable": False,
    }
    engine.dispose()


@pytest.mark.asyncio
async def test_live_stop_authorization_uses_durable_owner_and_purpose(tmp_path) -> None:
    engine, Session, clock, _inspector, coordinator = make_coordinator(
        tmp_path, "live-stop.db"
    )
    live = await coordinator.reserve(
        channel_key="live-stop-channel",
        auth_key=None,
        purpose="LIVE",
        owner_user_id=7,
        live_session_id="session-7",
    )
    live = await coordinator.activate(
        channel_key=live.channel_key,
        generation=live.generation,
        process_pid=701,
        process_group_id=701,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="birth-701",
    )
    _inspector.alive_fingerprints.add("birth-701")

    authorized = await coordinator.assert_stop_authorized(
        channel_key=live.channel_key,
        generation=live.generation,
        process_pid=701,
        process_group_id=701,
        process_start_fingerprint="birth-701",
        expected_purpose="LIVE",
        requesting_owner_user_id=7,
    )
    assert authorized.live_session_id == "session-7"

    for generation, owner_user_id in ((live.generation, 8), (0, 7)):
        with pytest.raises(PermissionError):
            await coordinator.assert_stop_authorized(
                channel_key=live.channel_key,
                generation=generation,
                process_pid=701,
                process_group_id=701,
                process_start_fingerprint="birth-701",
                expected_purpose="LIVE",
                requesting_owner_user_id=owner_user_id,
            )

    recording = await coordinator.reserve(
        channel_key="recording-stop-channel",
        auth_key=None,
        purpose="RECORDING",
        recording_id=17,
    )
    recording = await coordinator.activate(
        channel_key=recording.channel_key,
        generation=recording.generation,
        process_pid=702,
        process_group_id=702,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="birth-702",
    )
    _inspector.alive_fingerprints.add("birth-702")
    for purpose in ("RECORDING", "RECOVERY"):
        with Session() as db:
            lease = (
                db.query(TwitchUpstreamLease)
                .filter_by(channel_key=recording.channel_key)
                .one()
            )
            lease.purpose = purpose
            db.commit()
        with pytest.raises(PermissionError):
            await coordinator.assert_stop_authorized(
                channel_key=recording.channel_key,
                generation=recording.generation,
                process_pid=702,
                process_group_id=702,
                process_start_fingerprint="birth-702",
                expected_purpose="LIVE",
                requesting_owner_user_id=7,
            )
    engine.dispose()


@pytest.mark.asyncio
async def test_recovery_rejects_merely_released_live_process(tmp_path) -> None:
    engine, Session, clock, inspector, coordinator = make_coordinator(
        tmp_path, "recovery-guard.db"
    )
    reservation = await coordinator.reserve(
        channel_key="recovery-guard-channel",
        auth_key=None,
        purpose="RECORDING",
        recording_id=23,
    )
    active = await coordinator.activate(
        channel_key=reservation.channel_key,
        generation=reservation.generation,
        process_pid=801,
        process_group_id=801,
        process_started_at=clock.utcnow(),
        process_start_fingerprint="birth-801",
    )
    inspector.alive_fingerprints.add("birth-801")
    clock.advance(31)
    assert await coordinator.release(
        channel_key=active.channel_key,
        generation=active.generation,
        reason="recording_stopped",
    )

    with pytest.raises(TwitchUpstreamConflict) as raised:
        await coordinator.reserve(
            channel_key=active.channel_key,
            auth_key=None,
            purpose="RECOVERY",
            recording_id=23,
            expected_generation=active.generation,
        )

    assert raised.value.reason == "recovery_precondition_failed"
    with Session() as db:
        lease = db.query(TwitchUpstreamLease).one()
        assert (lease.state, lease.purpose, lease.generation) == (
            "RELEASED",
            "RECORDING",
            active.generation,
        )
    engine.dispose()
