from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    Recording,
    Stream,
    Streamer,
    StreamMetadata,
    TwitchUpstreamLease,
    TwitchUpstreamCoordinationState,
    User,
)


ROOT = Path(__file__).resolve().parents[1]


def test_state_persistence_process_exists_has_os_fallback() -> None:
    source = (ROOT / "app/services/core/state_persistence_service.py").read_text(
        encoding="utf-8"
    )

    assert "if not pid or pid <= 0:" in source
    assert "os.kill(pid, 0)" in source
    assert "except ProcessLookupError:" in source
    assert "except PermissionError:" in source


def test_startup_recovery_defers_when_live_status_cannot_be_verified() -> None:
    source = (ROOT / "app/services/recording/startup_recovery.py").read_text(
        encoding="utf-8"
    )

    api_error_block = source.split("except Exception as api_error:", 1)[1]
    api_error_block = api_error_block.split("if is_still_live:", 1)[0]

    assert "Deferring zombie recording cleanup" in api_error_block
    assert "continue" in api_error_block
    assert "is_still_live = False" not in api_error_block


def test_process_manager_psutil_flag_reflects_import_result() -> None:
    source = (ROOT / "app/services/recording/process_manager.py").read_text(
        encoding="utf-8"
    )

    assert "import psutil" in source
    assert "HAS_PSUTIL = True" in source
    assert "HAS_PSUTIL = False" in source
    assert "self.psutil_available = HAS_PSUTIL" in source


@pytest.fixture
def recovery_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery.db'}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Streamer.__table__,
            Stream.__table__,
            Recording.__table__,
            TwitchUpstreamLease.__table__,
            StreamMetadata.__table__,
            TwitchUpstreamCoordinationState.__table__,
        ],
    )
    Session = sessionmaker(bind=engine)
    now = datetime.now(timezone.utc)
    with Session() as db:
        streamer = Streamer(twitch_id="stable-channel-id", username="streamer")
        db.add(streamer)
        db.flush()
        stream = Stream(streamer_id=streamer.id, started_at=now - timedelta(hours=1))
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id,
            start_time=now - timedelta(minutes=30),
            status="recording",
            duration=17,
        )
        db.add(recording)
        db.flush()
        lease = TwitchUpstreamLease(
            channel_key=streamer.twitch_id,
            auth_key=None,
            recording_id=recording.id,
            purpose="RECORDING",
            state="ACTIVE",
            generation=11,
            process_pid=501,
            process_group_id=501,
            process_started_at=now - timedelta(hours=1),
            process_start_fingerprint="dead-process-501",
            reserved_at=now - timedelta(hours=1),
            activated_at=now - timedelta(hours=1),
            heartbeat_at=now - timedelta(minutes=5),
            expires_at=now - timedelta(minutes=4),
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=5),
        )
        db.add(lease)
        db.commit()
        values = {
            "recording_id": recording.id,
            "stream_id": stream.id,
            "streamer_id": streamer.id,
        }
    yield Session, values
    engine.dispose()


@pytest.mark.asyncio
async def test_unified_failed_resume_preserves_recoverable_recording(
    monkeypatch, recovery_database, tmp_path
):
    from app.services.recording import unified_recovery_service

    Session, values = recovery_database
    calls = []

    class RecordingService:
        def is_stream_active(self, stream_id):
            return False

        async def start_recording(self, stream_id, streamer_id, **kwargs):
            with Session() as db:
                prior = db.get(Recording, values["recording_id"])
                assert prior.status == "recording"
                assert prior.end_time is None
                assert prior.duration == 17
            calls.append((stream_id, streamer_id, kwargs))
            return None

    monkeypatch.setattr(unified_recovery_service, "SessionLocal", Session)
    monkeypatch.setattr(
        unified_recovery_service, "get_recording_manager", lambda: RecordingService()
    )

    service = unified_recovery_service.UnifiedRecoveryService()
    resumed = await service._resume_live_recording(
        values["recording_id"], tmp_path, "streamer"
    )

    assert resumed is False
    assert calls == [
        (
            values["stream_id"],
            values["streamer_id"],
            {
                "resume_segments_dir": str(tmp_path),
                "recovery_generation": 11,
            },
        )
    ]
    with Session() as db:
        prior = db.get(Recording, values["recording_id"])
        assert prior.status == "recording"
        assert prior.end_time is None
        assert prior.duration == 17


@pytest.mark.asyncio
@pytest.mark.parametrize("capture", ["ALIVE", "UNKNOWN"])
async def test_startup_skips_provider_and_admission_without_proven_capture_death(
    monkeypatch, recovery_database, capture
):
    from types import SimpleNamespace
    from app.services.recording import startup_recovery
    from app.services.recording.media_ownership import CaptureState
    from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator

    sessions, values = recovery_database
    calls = []

    async def provider(**kwargs):
        calls.append(("provider", kwargs))
        return [{"id": "synthetic-live"}]

    async def admission(**kwargs):
        calls.append(("admission", kwargs))

    async def snapshots():
        return {}

    monkeypatch.setattr(
        startup_recovery, "capture_state", lambda *_: CaptureState[capture]
    )
    processes = SimpleNamespace(
        capture_process_snapshot=snapshots,
        upstream_coordinator=TwitchUpstreamCoordinator(
            sessions, monotonic_clock=__import__("time").monotonic
        ),
    )
    owner = SimpleNamespace(
        process_manager=processes,
        is_stream_active=lambda _: False,
        start_recording=admission,
    )
    await startup_recovery.recover_startup_recordings(
        sessions, owner, SimpleNamespace(get_streams=provider)
    )
    assert calls == []
    with sessions() as db:
        row = db.get(Recording, values["recording_id"])
        assert (row.status, row.end_time, row.duration) == ("recording", None, 17)


@pytest.mark.asyncio
async def test_unified_success_stops_prior_only_after_fenced_resume(
    monkeypatch, recovery_database, tmp_path
):
    from app.services.recording import unified_recovery_service

    Session, values = recovery_database
    loop_thread = get_ident()
    queries = []
    preparation_queries = []
    with Session() as db:
        engine = db.get_bind()
    event.listen(
        engine, "before_cursor_execute", lambda *_: queries.append(get_ident())
    )

    class RecordingService:
        async def start_recording(self, stream_id, streamer_id, **kwargs):
            preparation_queries.extend(queries)
            assert engine.pool.checkedout() == 0
            with Session() as db:
                prior = db.get(Recording, values["recording_id"])
                assert prior.status == "recording"
                assert prior.end_time is None
            assert kwargs["recovery_generation"] == 11
            queries.clear()  # Exclude the upstream-boundary fixture's own readback.
            return 99

    monkeypatch.setattr(unified_recovery_service, "SessionLocal", Session)
    monkeypatch.setattr(
        unified_recovery_service, "get_recording_manager", lambda: RecordingService()
    )
    monkeypatch.setattr(
        unified_recovery_service.logging_service,
        "log_post_processing_activity",
        lambda *args, **kwargs: None,
    )

    service = unified_recovery_service.UnifiedRecoveryService()
    resumed = await service._resume_live_recording(
        values["recording_id"], tmp_path, "streamer"
    )

    assert resumed is True
    assert preparation_queries and loop_thread not in preparation_queries
    assert queries and loop_thread not in queries
    assert engine.pool.checkedout() == 0
    with Session() as db:
        prior = db.get(Recording, values["recording_id"])
        assert prior.status == "stopped"
        assert prior.end_time is not None
        assert prior.duration > 17


@pytest.mark.asyncio
async def test_unified_recovery_rejects_lease_for_other_recording(
    monkeypatch, recovery_database, tmp_path
):
    from app.services.recording import unified_recovery_service

    Session, values = recovery_database
    with Session() as db:
        lease = db.query(TwitchUpstreamLease).one()
        lease.recording_id = None
        db.commit()

    class RecordingService:
        async def start_recording(self, *args, **kwargs):
            raise AssertionError("recovery bypassed the persisted recording owner")

    monkeypatch.setattr(unified_recovery_service, "SessionLocal", Session)
    monkeypatch.setattr(
        unified_recovery_service, "get_recording_manager", lambda: RecordingService()
    )

    service = unified_recovery_service.UnifiedRecoveryService()
    resumed = await service._resume_live_recording(
        values["recording_id"], tmp_path, "streamer"
    )

    assert resumed is False
    with Session() as db:
        prior = db.get(Recording, values["recording_id"])
        assert prior.status == "recording"
        assert prior.end_time is None


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_failure", [False, True])
async def test_startup_failed_resume_preserves_recoverable_recording(
    monkeypatch, recovery_database, provider_failure
):
    import importlib

    import app.database
    from app.services.api.twitch_api import twitch_api

    startup_init = importlib.import_module("app.services.init.startup_init")

    Session, values = recovery_database
    calls = []

    import subprocess
    import sys
    import time
    from types import SimpleNamespace
    from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator

    dead = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    dead.wait(timeout=5)
    with Session() as db:
        lease = db.query(TwitchUpstreamLease).one()
        lease.process_pid = dead.pid
        lease.process_group_id = dead.pid
        db.commit()

    async def snapshots():
        return {}

    provider_calls = []

    async def live_status(**kwargs):
        assert Session.kw["bind"].pool.checkedout() == 0
        assert kwargs == {"user_ids": ["stable-channel-id"]}
        provider_calls.append(kwargs)
        if provider_failure:
            raise RuntimeError("synthetic provider unavailable")
        return [{"id": "synthetic-live"}]

    class RecordingService:
        def is_stream_active(self, stream_id):
            return False

        async def start_recording(self, stream_id, streamer_id, **kwargs):
            assert Session.kw["bind"].pool.checkedout() == 0, (
                "startup must close its catalog before admission"
            )
            with Session() as db:
                prior = db.get(Recording, values["recording_id"])
                assert prior.status == "recording"
                assert prior.end_time is None
                assert prior.duration == 17
            calls.append((stream_id, streamer_id, kwargs))
            return None

    async def live(**kwargs):
        assert Session.kw["bind"].pool.checkedout() == 0
        return [{"id": "fixture-live"}]

    monkeypatch.setattr(app.database, "SessionLocal", Session)
    RecordingService.process_manager = SimpleNamespace(
        capture_process_snapshot=snapshots,
        upstream_coordinator=TwitchUpstreamCoordinator(
            Session, monotonic_clock=time.monotonic
        ),
    )
    monkeypatch.setattr(twitch_api, "get_streams", live_status)
    monkeypatch.setattr(
        startup_init, "get_recording_manager", lambda: RecordingService()
    )
    await startup_init.cleanup_zombie_recordings()

    assert provider_calls == [{"user_ids": ["stable-channel-id"]}]
    assert calls == (
        []
        if provider_failure
        else [
            (
                values["stream_id"],
                values["streamer_id"],
                {
                    "force_mode": True,
                    "resume_segments_dir": None,
                    "recovery_generation": 11,
                },
            )
        ]
    )
    with Session() as db:
        prior = db.get(Recording, values["recording_id"])
        assert prior.status == "recording"
        assert prior.end_time is None
        assert prior.duration == 17
