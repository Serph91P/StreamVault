"""Recovery observation/refusal uses own catalog/cache and closes native faults.

Value: protects=owned recovery cache discrimination and failed observation refusal;
fails_when=peer fallback, self/other-stream cache match, leaked SQL scope or false resume;
why_new=existing real discovery/control covers catalog active rows but not these cache/fault inputs;
seam=none; no_claim=durable capture authority, provider/media execution or successful resume.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Recording, Stream
from app.services.recording.unified_recovery_service import UnifiedRecoveryService
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,expected",
    [
        ("cache-other-record", True),
        ("cache-self", False),
        ("cache-other-stream", False),
        ("missing-record", False),
        ("sql-activity-denial", False),
        ("sql-live-denial", False),
        ("resume-missing", False),
        ("sql-resume-denial", False),
        ("fuzzy-path-lookup", 7),
        ("sql-path-lookup-denial", None),
    ],
)
async def test_owned_recovery_observation_and_refusal_close_native_scopes(
    image_applications, monkeypatch, case, expected
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]

    def seed():
        for owner in databases:
            with owner.sync_session_factory() as db:
                db.add(Stream(id=70, streamer_id=1))
                db.flush()
                db.add(
                    Recording(
                        id=7,
                        stream_id=70,
                        status="stopped",
                        path=str(
                            Path(app.state.settings.RECORDING_DIRECTORY)
                            / "alice"
                            / "capture_backup.ts"
                        ),
                        start_time=datetime.now(timezone.utc),
                    )
                )
                db.commit()

    await run_in_thread_pool(seed)
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    service = UnifiedRecoveryService(
        session_factory=database.sync_session_factory,
        settings=app.state.settings,
        recording_manager=manager,
        queue_service=app.state.background_queue_service,
    )
    if case.startswith("cache-"):
        manager.orchestrator.state_manager.add_active_recording(
            7 if case == "cache-self" else 17,
            {"stream_id": 71 if case == "cache-other-stream" else 70},
        )
    import app.services.recording.unified_recovery_service as recovery

    monkeypatch.setattr(recovery, "SessionLocal", databases[1].sync_session_factory)
    queries, listeners = [], []
    for index, owner in enumerate(databases):

        def observe(*_args, index=index):
            queries.append((index, get_ident()))
            if index == 0 and case.startswith("sql-"):
                raise sqlite3.OperationalError("synthetic-owned-recovery-read-denial")

        event.listen(owner.sync_engine, "before_cursor_execute", observe)
        listeners.append(observe)
    try:
        if case in {"fuzzy-path-lookup", "sql-path-lookup-denial"}:
            directory = Path(app.state.settings.RECORDING_DIRECTORY) / "alice"
            known, missing = (
                str(directory / "capture.ts"),
                str(directory / "not-found.ts"),
            )
            found = await service._batch_find_recordings_by_paths([known, missing])
            assert found == {known: expected, missing: None}
        else:
            if case in {"resume-missing", "sql-resume-denial"}:
                result = await service._resume_live_recording(
                    999 if case == "resume-missing" else 7,
                    Path(app.state.settings.RECORDING_DIRECTORY),
                    "fixture",
                )
            elif case == "sql-live-denial":
                result = await service._check_if_streamer_still_live(7)
            else:
                result = await service._check_if_stream_has_active_recording(
                    999 if case == "missing-record" else 7
                )
            assert result is expected
        assert queries and {owner for owner, _thread in queries} == {0}
        assert get_ident() not in {thread for _owner, thread in queries}
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        assert all(
            not item.state.background_queue_service.external_tasks for item in apps
        )
    finally:
        for owner, listener in zip(databases, listeners, strict=True):
            event.remove(owner.sync_engine, "before_cursor_execute", listener)
        await close_owned(apps)
    for owner in databases:
        with owner.sync_session_factory() as db:
            row = db.query(Recording).one()
            assert row.id == 7 and row.status == "stopped" and row.end_time is None
        assert owner.sync_engine.pool.checkedout() == 0
