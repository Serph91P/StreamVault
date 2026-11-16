"""Registered queue callbacks skip deleted own streams before media effects."""

from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event

from app.models import RecordingProcessingState, Stream
from app.services.queues.task_progress_tracker import TaskStatus
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [
        "metadata_generation",
        "chapters_generation",
        "mp4_remux",
        "thumbnail_generation",
        "mp4_validation",
    ],
)
async def test_registered_processing_callback_skips_deleted_owner_not_existing_peer(
    image_applications, monkeypatch, kind
):
    apps, databases, _clients, _ = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    root = Path(apps[0].state.settings.RECORDING_DIRECTORY)
    source, output = root / "source.ts", root / "output.mp4"
    source.write_bytes(b"source unchanged by skipped job")
    output.write_bytes(b"output unchanged by skipped job")

    def seed_peer():
        with databases[1].sync_session_factory() as db:
            db.add(Stream(id=70, streamer_id=1, title="Only the peer has this stream"))
            db.commit()

    await run_in_thread_pool(seed_peer)
    own, manager = (
        apps[0].state.background_queue_service,
        apps[0].state.background_queue_manager,
    )
    results = []
    native_register = own.register_task_handler

    def register(name, handler):
        if name == kind:

            async def observed(payload, progress=None):
                result = await handler(payload, progress)
                results.append(result)
                return result

            return native_register(name, observed)
        return native_register(name, handler)

    monkeypatch.setattr(own, "register_task_handler", register)
    queries = []
    listeners = []
    for index, database in enumerate(databases):

        def listener(*_args, index=index):
            queries.append((index, get_ident()))

        event.listen(database.sync_engine, "before_cursor_execute", listener)
        listeners.append(listener)
    try:
        await manager.initialize()
        before_files = {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        identity = await own.enqueue_task(
            kind,
            {
                "stream_id": 70,
                "recording_id": 7,
                "base_filename": "output",
                "output_dir": str(root),
                "ts_file_path": str(source),
                "mp4_output_path": str(output),
                "mp4_path": str(output),
                "streamer_name": "owner-0",
            },
            max_retries=0,
        )
        await own.wait_for_completion(timeout=10)
        assert own.get_task(identity).status is TaskStatus.COMPLETED
        assert results == [{"status": "skipped", "reason": "stream_deleted"}]
        assert queries and {owner for owner, _thread in queries} == {0}
        assert get_ident() not in {thread for _owner, thread in queries}
        for database, listener in zip(databases, listeners, strict=True):
            event.remove(database.sync_engine, "before_cursor_execute", listener)
            with database.sync_session_factory() as db:
                assert db.query(RecordingProcessingState).count() == 0
        assert source.read_bytes() == b"source unchanged by skipped job"
        assert output.read_bytes() == b"output unchanged by skipped job"
        assert {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        } == before_files
    finally:
        for database, listener in zip(databases, listeners, strict=True):
            if event.contains(database.sync_engine, "before_cursor_execute", listener):
                event.remove(database.sync_engine, "before_cursor_execute", listener)
        await close_owned(apps)
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
