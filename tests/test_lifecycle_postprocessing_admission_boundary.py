"""Native lifecycle media-task admission owns its catalog and filesystem boundary.

Value: protects=owned queue dependency graph, missing-input refusals and worker reads;
fails_when=late segment check blocks loop, refusal admits tasks or owners cross;
why_new=completion probes watched TS only, not cleanup discovery and native admission rows;
seam=none; no_claim=executed media tasks or provider capture; queue admission only.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import BackgroundTask, Recording, Stream
from app.models.background_task import BackgroundTaskDependency
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode",
    [
        "ordinary",
        "late-segments",
        "segments",
        "empty-segments",
        "missing-recording",
        "missing-path",
        "missing-file",
    ],
)
async def test_native_postprocessing_admission_checks_late_segments_in_worker(
    image_applications, monkeypatch, mode
):
    apps, databases, _clients, _ = image_applications
    loop_thread = get_ident()
    late_segments = mode == "late-segments"
    output = Path(apps[0].state.settings.RECORDING_DIRECTORY) / "capture.ts"
    output.write_bytes(b"synthetic-owned-admission-not-media")
    segments = output.with_name("capture_segments")
    if mode in {"segments", "empty-segments"}:
        segments.mkdir()
        if mode == "segments":
            for number in (2, 1):
                (segments / f"capture_part{number:03}.ts").write_bytes(
                    b"synthetic-owned-segment"
                )
    if mode == "missing-file":
        output.unlink()
    with databases[0].sync_session_factory() as db:
        db.add(Stream(id=70, streamer_id=1, title="owned admission"))
        db.flush()
        db.add(
            Recording(
                id=7,
                stream_id=70,
                status="completed",
                path=None if mode == "missing-path" else str(output),
                start_time=datetime.now(timezone.utc),
            )
        )
        db.commit()
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0], "headers": []}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    native_enqueue = lifecycle.queue_service.enqueue_task_with_dependencies
    native_stat = os.stat
    probes, queries, listeners = [], [], []

    async def enqueue_then_create_segments(*args, **kwargs):
        result = await native_enqueue(*args, **kwargs)
        if args[0] == "metadata_generation" and late_segments:
            segments.mkdir()
            (segments / "part001.ts").write_bytes(b"synthetic-late-owned-segment")
        return result

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path) == str(
            segments
        ):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        for index, database in enumerate(databases):

            def observe(*_args, index=index):
                queries.append((index, get_ident()))

            event.listen(database.sync_engine, "before_cursor_execute", observe)
            listeners.append(observe)
        with monkeypatch.context() as scoped:
            scoped.setattr(os, "stat", stat)
            scoped.setattr(
                lifecycle.queue_service,
                "enqueue_task_with_dependencies",
                enqueue_then_create_segments,
            )
            await lifecycle._trigger_post_processing(
                999 if mode == "missing-recording" else 7
            )
        assert queries and all(
            index == 0 and thread != loop_thread for index, thread in queries
        )
        if mode in {"missing-recording", "missing-path"}:
            assert probes == []
        else:
            assert probes and loop_thread not in probes
        for database, listener in zip(databases, listeners, strict=True):
            event.remove(database.sync_engine, "before_cursor_execute", listener)
        listeners.clear()
        with databases[0].sync_session_factory() as db:
            tasks = db.query(BackgroundTask).all()
            dependencies = {
                (row.task_id, row.dependency_id)
                for row in db.query(BackgroundTaskDependency).all()
            }
            if mode in {"ordinary", "late-segments"}:
                assert {task.task_type for task in tasks} == {
                    "metadata_generation",
                    "mp4_remux",
                    "thumbnail_generation",
                    "cleanup",
                }
                assert len(tasks) == 4
                cleanup = next(task for task in tasks if task.task_type == "cleanup")
                payload = cleanup.payload
                by_type = {task.task_type: task.id for task in tasks}
                assert dependencies == {
                    (by_type["mp4_remux"], by_type["metadata_generation"]),
                    (by_type["thumbnail_generation"], by_type["mp4_remux"]),
                    (by_type["cleanup"], by_type["thumbnail_generation"]),
                }
                assert payload["recording_id"] == 7 and payload["stream_id"] == 70
                assert payload["files_to_remove"] == [str(output)] + (
                    [str(segments)] if late_segments else []
                )
            elif mode == "segments":
                assert len(tasks) == 1 and tasks[0].task_type == "segment_concatenation"
                payload = tasks[0].payload
                assert payload["recording_id"] == 7 and payload["stream_id"] == 70
                assert payload["output_path"] == str(output)
                assert payload["segment_files"] == [
                    str(segments / f"capture_part{number:03}.ts") for number in (1, 2)
                ]
                assert dependencies == set()
            else:
                assert tasks == [] and dependencies == set()
            assert db.get(Recording, 7).status == "completed"
        with databases[1].sync_session_factory() as db:
            assert db.query(BackgroundTask).count() == 0
        if mode == "missing-file":
            assert not output.exists()
        else:
            assert output.read_bytes() == b"synthetic-owned-admission-not-media"
        assert not lifecycle.process_manager.active_processes
    finally:
        for database, listener in zip(databases, listeners):
            event.remove(database.sync_engine, "before_cursor_execute", listener)
        await close_owned(apps)
