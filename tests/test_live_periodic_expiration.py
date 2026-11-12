"""Periodic live expiration exercises actual leases, pipes, children and cleanup."""

import asyncio
from datetime import datetime, timedelta, timezone
import importlib

import pytest

from tests import test_live_lease_loss_cleanup

live = test_live_lease_loss_cleanup.live


@pytest.mark.asyncio
@pytest.mark.parametrize("clock_state", ["expired", "current", "invalid-clock"])
async def test_one_periodic_sweep_cleans_only_expired_owned_capture(
    live, monkeypatch, caplog, clock_state
):
    service, session, _, _, _, pipe = live
    if clock_state == "expired":
        session.last_accessed = datetime.utcnow() - timedelta(days=1)
    elif clock_state == "invalid-clock":
        # An inconsistent restored clock must fail safely, not terminate a writer.
        session.last_accessed = datetime.now(timezone.utc)
    module = importlib.import_module("app.services.live_streaming_service")

    class SweepClock:
        def __init__(self):
            self.sweeps = 0

        def __getattr__(self, name):
            return getattr(asyncio, name)

        async def sleep(self, interval):
            if interval != 30:
                return await asyncio.sleep(interval)
            self.sweeps += 1
            if self.sweeps == 2:
                raise asyncio.CancelledError
            # Drive one scheduled sweep, not a claim of 30 seconds elapsed.
            await asyncio.sleep(0)

    clock = SweepClock()
    monkeypatch.setattr(module, "asyncio", clock)
    await asyncio.wait_for(service._cleanup_loop(), 5)
    assert clock.sweeps == 2
    if clock_state == "expired":
        assert session.session_id not in service.sessions
        assert session.streamlink_process.returncode is not None
        assert session.ffmpeg_process.returncode is not None and pipe.done()
        assert not session.output_dir.exists()
    else:
        assert service.sessions[session.session_id] is session
        assert session.streamlink_process.returncode is None
        assert session.ffmpeg_process.returncode is None and not pipe.done()
        assert (
            session.output_dir.joinpath("fragment.ts").read_bytes()
            == b"owned synthetic fragment"
        )
        if clock_state == "invalid-clock":
            assert "Error in cleanup loop" in caplog.text


@pytest.mark.asyncio
async def test_monitor_missing_or_already_inactive_session_does_not_stop_peer(live):
    service, session, _, _, _, pipe = live
    await service._monitor_session("absent")
    session.is_active = False
    await service._monitor_session(session.session_id)
    assert session.streamlink_process.returncode is None
    assert session.ffmpeg_process.returncode is None and not pipe.done()
    assert session.session_id in service.sessions
