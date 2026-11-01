"""Exercise recording completion composition against real persistence values."""

import importlib
from types import SimpleNamespace

import pytest

from app.database import Base, DatabaseLifecycle
from app.models import Streamer
from app.services.recording.recording_database_service import RecordingDatabaseService


@pytest.mark.asyncio
async def test_completion_callback_uses_persisted_start_time_and_awaits_reads(
    tmp_path, monkeypatch
):
    module = importlib.import_module("app.services.recording.recording_orchestrator")
    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'callback.db'}")
    captured = {}
    delivered = []

    def process_manager(**kwargs):
        captured["callback"] = kwargs["post_processing_callback"]
        return SimpleNamespace()

    async def enqueue(recording_id, path, metadata):
        delivered.append((recording_id, path, metadata))

    # Isolate filesystem/provider/process construction, not persistence or callback logic.
    for name in (
        "RecordingStateManager",
        "RecordingWebSocketService",
        "RecordingLogger",
        "NotificationManager",
        "StreamInfoManager",
        "RecordingLifecycleManager",
    ):
        monkeypatch.setattr(module, name, lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(module, "ProcessManager", process_manager)
    monkeypatch.setattr(
        module,
        "PostProcessingCoordinator",
        lambda *args: SimpleNamespace(enqueue_post_processing=enqueue),
    )
    try:
        with lifecycle.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with lifecycle.sync_session_factory() as session:
            session.add(Streamer(id=1, username="owner", twitch_id="owner"))
            session.commit()
        service = RecordingDatabaseService(
            session_factory=lambda: lifecycle.sync_session_factory()
        )
        stream = await service.create_stream(
            {"streamer_id": 1, "twitch_stream_id": "stream"}
        )
        recording = await service.create_recording(stream.id, "capture.ts")
        monkeypatch.setattr(module, "RecordingDatabaseService", lambda _db: service)
        module.RecordingOrchestrator()
        await captured["callback"](recording.id, "complete.mp4")
        completed = await service.get_recording(recording.id)
        assert completed.status == "completed" and completed.path == "complete.mp4"
        assert delivered == [
            (
                recording.id,
                "complete.mp4",
                {
                    "streamer_name": "owner",
                    "started_at": recording.start_time.isoformat(),
                    "stream_id": stream.id,
                    "recording_id": recording.id,
                },
            )
        ]
    finally:
        await lifecycle.adispose()
