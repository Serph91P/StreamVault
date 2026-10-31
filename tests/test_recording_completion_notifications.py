"""Completion producers must deliver duration through the real external formatter.

Only child processes and the final Apprise transport are controlled. ORM reads,
notification toggles, URL handling, formatting and segment finalization stay real.
"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace

import apprise
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import GlobalSettings, Stream, Streamer, StreamerRecordingSettings
from app.services.notifications.external_notification_service import (
    ExternalNotificationService,
)
from app.services.recording.process_manager import ProcessManager


@pytest.fixture
def completion_state(monkeypatch, tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        streamer = Streamer(username="synthetic963", twitch_id="synthetic963")
        db.add(streamer)
        db.flush()
        stream = Stream(streamer_id=streamer.id, title="Synthetic completion")
        db.add(stream)
        db.add(StreamerRecordingSettings(streamer_id=streamer.id, quality="720p"))
        db.add(
            GlobalSettings(
                notifications_enabled=True,
                notify_recording_completed=True,
                notification_url="ntfy://localhost/synthetic963",
            )
        )
        db.commit()
        stream_id = stream.id
    monkeypatch.setattr("app.database.SessionLocal", sessions)
    monkeypatch.setattr(
        "app.services.notifications.external_notification_service.SessionLocal",
        sessions,
    )

    delivered = []
    details = []

    async def transport(self, **payload):
        delivered.append(payload)
        return True

    monkeypatch.setattr(apprise.Apprise, "async_notify", transport)
    real_send = ExternalNotificationService.send_recording_notification

    async def observe_details(self, **payload):
        details.append(dict(payload["details"]))
        return await real_send(self, **payload)

    monkeypatch.setattr(
        ExternalNotificationService, "send_recording_notification", observe_details
    )
    state = SimpleNamespace(
        sessions=sessions,
        stream_id=stream_id,
        delivered=delivered,
        details=details,
        root=tmp_path,
    )
    yield state
    engine.dispose()


class CompletedChild:
    pid = 963

    def __init__(self, *, timeout=False):
        self.returncode = 0
        self.timeout = timeout

    async def communicate(self):
        return b"", b""

    def terminate(self):
        pass

    async def wait(self):
        if self.timeout:
            self.timeout = False
            raise asyncio.TimeoutError
        return self.returncode

    def kill(self):
        self.returncode = -9


def make_manager(state, child):
    manager = object.__new__(ProcessManager)
    manager.active_processes = {f"stream_{state.stream_id}": child}
    manager.long_stream_processes = {}
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    return manager


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["monitor", "stop", "stop_timeout"])
@pytest.mark.parametrize(
    "seconds, minutes, rendered",
    [
        (9005, 150, "2h 30m"),
        (1865, 31, "31m"),
        (0, 0, "0m"),
        (None, 0, "0m"),
    ],
)
async def test_segmented_completion_delivers_duration_once(
    completion_state,
    monkeypatch,
    entry,
    seconds,
    minutes,
    rendered,
):
    state = completion_state
    child = CompletedChild(timeout=entry == "stop_timeout")
    manager = make_manager(state, child)
    segment_dir = state.root / "segments"
    segment_dir.mkdir()
    segment = segment_dir / "synthetic_part001.ts"
    segment.write_bytes(b"synthetic media")
    output = segment_dir / "synthetic.ts"
    info = {
        "stream_id": state.stream_id,
        "recording_id": 963,
        "segment_dir": str(segment_dir),
        "base_output_path": str(output),
        "total_segments": [{"path": str(segment)}],
        "monitor_task": None,
        "segment_start_time": (
            datetime.now() - timedelta(seconds=seconds) if seconds is not None else None
        ),
    }
    manager.long_stream_processes[f"stream_{state.stream_id}"] = info

    async def concatenate(*args, **kwargs):
        assert args[0] == "ffmpeg"
        assert "synthetic_part001.ts" in (segment_dir / "concat_list.txt").read_text()
        output.write_bytes(segment.read_bytes())
        return CompletedChild()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", concatenate)
    processed = []

    async def postprocess(recording_id, path):
        processed.append((recording_id, path))

    manager.post_processing_callback = postprocess
    if entry == "monitor":
        assert await manager.monitor_process(child) == 0
    else:
        assert await manager.terminate_process(f"stream_{state.stream_id}") is True

    # Repeat callers after ownership was consumed: no second completion/send.
    assert await manager.terminate_process(f"stream_{state.stream_id}") is True
    assert manager.active_processes == {}
    assert manager.long_stream_processes == {}
    assert processed == [(963, str(state.root / "synthetic.ts"))]
    assert (state.root / "synthetic.ts").read_bytes() == b"synthetic media"
    assert len(state.delivered) == 1
    assert f"Duration: {rendered}\n" in state.delivered[0]["body"]
    assert "Quality: 720p" in state.delivered[0]["body"]
    assert state.delivered[0]["title"] == "✅ Recording Completed: synthetic963"
    assert state.details == [
        {"duration_minutes": minutes, "file_size_mb": "0.00", "quality": "720p"}
    ]
    assert type(state.details[0]["duration_minutes"]) is int


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seconds, rendered", [(9005, "2h 30m"), (1865, "31m"), (0, "0m"), (None, "0m")]
)
async def test_single_file_completion_uses_same_duration_contract(
    completion_state, seconds, rendered
):
    state = completion_state
    output = state.root / "synthetic.ts"
    output.write_bytes(b"synthetic media")
    with state.sessions() as db:
        stream = db.get(Stream, state.stream_id)
        stream.recording_path = str(output)
        stream.started_at = datetime(2026, 1, 1)
        stream.ended_at = (
            stream.started_at + timedelta(seconds=seconds)
            if seconds is not None
            else None
        )
        db.commit()
    child = CompletedChild()
    manager = make_manager(state, child)
    assert await manager.monitor_process(child) == 0
    assert len(state.delivered) == 1
    assert f"Duration: {rendered}\n" in state.delivered[0]["body"]
    assert state.details[0].get("duration_minutes") == (
        seconds // 60 if seconds is not None else 0
    )
    assert type(state.details[0]["duration_minutes"]) is int


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "details, rendered",
    [
        ({}, "0m"),
        ({"duration_minutes": 0}, "0m"),
        ({"duration_minutes": 31}, "31m"),
        ({"duration_minutes": 150}, "2h 30m"),
    ],
)
async def test_existing_canonical_payload_still_delivers(
    completion_state, details, rendered
):
    state = completion_state
    assert (
        await ExternalNotificationService().send_recording_notification(
            streamer_name="synthetic963",
            event_type="recording_completed",
            details=details,
        )
        is True
    )
    assert len(state.delivered) == 1
    assert f"Duration: {rendered}\n" in state.delivered[0]["body"]


@pytest.mark.asyncio
async def test_disabled_completion_never_reaches_transport(completion_state):
    state = completion_state
    with state.sessions() as db:
        db.query(GlobalSettings).first().notify_recording_completed = False
        db.commit()
    assert (
        await ExternalNotificationService().send_recording_notification(
            streamer_name="synthetic963",
            event_type="recording_completed",
            details={"duration_minutes": 150},
        )
        is False
    )
    assert state.delivered == []
