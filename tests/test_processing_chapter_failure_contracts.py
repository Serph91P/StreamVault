"""Chapter callback failure persists owned state before propagating to queue.

Chapter generator is a controlled failure port; SQL/state remain native. No
chapter-format/media/provider success claim follows from this test.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.models import Recording, RecordingProcessingState, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["empty-result", "exception"])
async def test_chapter_callback_marks_native_owned_failure_and_propagates_error(
    image_applications, monkeypatch, failure
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]
    root = Path(app.state.settings.RECORDING_DIRECTORY)
    output = root / "fixture.mp4"
    output.write_bytes(b"untouched chapter failure-port fixture")

    def seed():
        with database.sync_session_factory() as db:
            db.add(Stream(id=70, streamer_id=1))
            db.flush()
            db.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="completed",
                    start_time=datetime.now(timezone.utc),
                )
            )
            db.commit()

    await run_in_thread_pool(seed)
    handler = app.state.background_queue_manager.task_handlers
    calls = []

    async def generate(**kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        calls.append(kwargs)
        if failure == "exception":
            raise RuntimeError("synthetic-owned-chapter-generator-failure")
        return None

    monkeypatch.setattr(
        handler.metadata_service, "ensure_all_chapter_formats", generate
    )
    threads = []

    def sql(*_args):
        threads.append(get_ident())

    event.listen(database.sync_engine, "before_cursor_execute", sql)
    try:
        with pytest.raises(
            Exception,
            match="Chapters generation failed"
            if failure == "empty-result"
            else "synthetic-owned-chapter-generator-failure",
        ):
            await handler.handle_chapters_generation(
                {"stream_id": 70, "recording_id": 7, "mp4_path": str(output)}
            )
        assert calls == [{"stream_id": 70, "mp4_path": str(output)}]
        assert threads and get_ident() not in threads
        event.remove(database.sync_engine, "before_cursor_execute", sql)
        with database.sync_session_factory() as db:
            state = db.query(RecordingProcessingState).one()
            assert state.recording_id == 7 and state.stream_id == 70
            assert state.chapters_status == "failed" and state.last_error
        with databases[1].sync_session_factory() as db:
            assert db.query(RecordingProcessingState).count() == 0
        assert output.read_bytes() == b"untouched chapter failure-port fixture"
    finally:
        if event.contains(database.sync_engine, "before_cursor_execute", sql):
            event.remove(database.sync_engine, "before_cursor_execute", sql)
        await close_owned(apps)
    assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
