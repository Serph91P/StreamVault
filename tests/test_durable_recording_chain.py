"""Production factory IDs are acknowledged only after durable admission."""

import importlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_queue_manager import TaskQueueManager


@pytest.mark.asyncio
@pytest.mark.parametrize("isolated", [False, True])
async def test_factory_admits_one_atomic_idempotent_durable_chain(tmp_path, monkeypatch, isolated):
    factory = importlib.import_module("app.services.processing.recording_task_factory")
    database = importlib.import_module("app.database")
    config = importlib.import_module("app.config.settings")
    engine = create_engine(f"sqlite:///{tmp_path / 'factory.db'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    monkeypatch.setattr(factory, "SessionLocal", sessions)
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(config.settings, "RECORDING_DIRECTORY", str(tmp_path))
    now = datetime.now(timezone.utc)
    with sessions() as db:
        channel = Streamer(username="factory-test", twitch_id="factory-test")
        db.add(channel)
        db.flush()
        stream = Stream(streamer_id=channel.id, started_at=now)
        db.add(stream)
        db.flush()
        recording = Recording(stream_id=stream.id, start_time=now, status="completed")
        db.add(recording)
        db.flush()
        db.add(RecordingProcessingState(recording_id=recording.id, stream_id=stream.id, streamer_id=channel.id))
        db.commit()
        stream_id, recording_id = stream.id, recording.id
    media = tmp_path / "source.ts"
    media.write_bytes(b"synthetic source must remain untouched during admission")
    store = DurableTaskStore(sessions)
    queue = TaskQueueManager(task_store=store, enable_streamer_isolation=isolated)
    payload = dict(stream_id=stream_id, recording_id=recording_id, ts_file_path=str(media),
                   output_dir=str(tmp_path), streamer_name="factory-test", started_at=now.isoformat())
    try:
        ids = await queue.enqueue_recording_post_processing(**payload)
        assert len(ids) == 6
        assert set(store.snapshot(ids)) == set(ids)
        assert store.counts() == {"pending": 6}
        assert await queue.enqueue_recording_post_processing(**payload) == ids
        assert store.counts() == {"pending": 6}
        with sessions() as db:
            state = db.query(RecordingProcessingState).filter_by(recording_id=recording_id).one()
            assert set(state.get_task_ids().values()) == set(ids)
        assert queue.get_task_status(ids[0]).value == "pending"
        assert len(queue.progress_tracker.active_tasks) == 0
        assert len(queue.dependency_manager.tasks) == 0
        assert media.read_bytes() == b"synthetic source must remain untouched during admission"
        # A later explicit recovery request can retry exhausted terminal rows;
        # replaying an already-pending chain above must not duplicate work.
        from app.models.background_task import BackgroundTask
        with sessions() as db:
            for task in db.query(BackgroundTask):
                task.status = "failed"
                task.retry_count = task.max_retries
            db.commit()
        assert await queue.enqueue_recording_post_processing(**payload) == ids
        assert store.counts() == {"pending": 6}
    finally:
        await queue.progress_tracker.cleanup_background_tasks()
        engine.dispose()
