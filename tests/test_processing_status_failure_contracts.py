"""Processing status invalid/failing writes leave actual catalogs recoverable.

Value: protects=unknown/missing status inputs and native SQL faults do not dirty peer or leak scopes;
fails_when=partial status row commits, wrong catalog or status scope survives fault;
why_new=existing status test covers success/socket cancellation, not native write/refresh faults;
seam=none; no_claim=media/provider execution or job completion from a status receipt.
"""

import sqlite3
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event

from app.models import Recording, RecordingProcessingState, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "missing-recording",
        "missing-stream",
        "unknown-step",
        "read-denied",
        "insert-denied",
        "refresh-denied",
    ],
)
async def test_native_processing_status_rejects_or_recovers_without_peer_effects(
    image_applications, case
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]

    def seed():
        for index, owner in enumerate(databases):
            with owner.sync_session_factory() as db:
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
                if index == 1:
                    db.add(
                        RecordingProcessingState(
                            recording_id=7,
                            stream_id=70,
                            streamer_id=1,
                            metadata_status="completed",
                        )
                    )
                db.commit()

    await run_in_thread_pool(seed)
    handler = app.state.background_queue_manager.task_handlers
    queries, listeners = [], []
    inserted, rejected = [], []
    for index, owner in enumerate(databases):

        def observe(_connection, _cursor, statement, *_args, index=index):
            queries.append((index, get_ident()))
            upper = statement.lstrip().upper()
            if index != 0:
                return
            state_read = (
                upper.startswith("SELECT") and "RECORDING_PROCESSING_STATE" in upper
            )
            state_insert = upper.startswith("INSERT INTO RECORDING_PROCESSING_STATE")
            if state_insert:
                inserted.append(True)
            deny = (
                case == "read-denied"
                and state_read
                or case == "insert-denied"
                and state_insert
                or case == "refresh-denied"
                and bool(inserted)
                and state_read
                and not rejected
            )
            if deny:
                rejected.append(True)
                raise sqlite3.OperationalError(
                    "synthetic-owned-processing-status-denial"
                )

        event.listen(owner.sync_engine, "before_cursor_execute", observe)
        listeners.append(observe)
    try:
        await handler._record_status(
            None if case == "missing-recording" else 7,
            999 if case == "missing-stream" else 70,
            "not-a-processing-step" if case == "unknown-step" else "metadata",
            "completed",
        )
        if case == "missing-recording":
            assert queries == []
        else:
            assert queries and {owner for owner, _thread in queries} == {0}
            assert get_ident() not in {thread for _owner, thread in queries}
        if case.endswith("denied"):
            assert rejected, "native fault was never exercised"
        assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
    finally:
        for owner, listener in zip(databases, listeners, strict=True):
            event.remove(owner.sync_engine, "before_cursor_execute", listener)
        await close_owned(apps)
    with database.sync_session_factory() as db:
        rows = db.query(RecordingProcessingState).all()
        if case == "refresh-denied":
            assert len(rows) == 1 and rows[0].metadata_status == "completed"
        else:
            assert rows == []
    with databases[1].sync_session_factory() as db:
        state = db.query(RecordingProcessingState).one()
        assert state.recording_id == 7 and state.metadata_status == "completed"
    assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
