"""Failure publication keeps its owning catalog closed across failing transports.

Deleting independent transport error handling or using a default catalog breaks
these effects. Only selected SQL/send operations fail; snapshots/queues/sockets
are real. No successful provider or physical notification delivery is claimed.
"""

from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event, select
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
async def test_failure_notification_sql_and_transport_faults_preserve_catalogs(
    image_applications,
    monkeypatch,
):
    apps, databases, _clients, _ = image_applications
    app = apps[0]
    facade = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    manager = facade.orchestrator.process_manager
    await run_in_thread_pool(seed_recording, databases[0])
    notifier = manager._get_external_notification_service()
    attempted = []

    async def external_denied(service, **kwargs):
        assert service._session_factory is databases[0].sync_session_factory
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        attempted.append(kwargs)
        raise OSError("synthetic external transport denial")

    async def socket_denied(_message):
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        raise OSError("synthetic socket transport denial")

    observed = []

    def deny_sql(_connection, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("SELECT"):
            observed.append(get_ident())
            raise RuntimeError("synthetic snapshot SQL denial")

    try:
        # Missing/malformed identities must not publish a failure for another stream.
        for identity in (None, "no-stream-id", "stream_999", "stream_invalid"):
            await manager._notify_recording_failed(identity, "not delivered")
            await manager._record_failure_in_database(identity, "not recorded", "test")
        assert await app.state.websocket_manager.get_events_since() == []
        assert await manager.get_recording_progress(11) is None

        with monkeypatch.context() as faults:
            faults.setattr(
                type(notifier), "send_recording_notification", external_denied
            )
            faults.setattr(
                app.state.websocket_manager, "send_notification", socket_denied
            )
            await manager._notify_recording_failed("stream_72", "delivery failure")
        assert len(attempted) == 1
        assert attempted[0]["streamer_name"] == "owner-0"
        assert attempted[0]["event_type"] == "recording_failed"
        assert attempted[0]["details"]["error_message"] == "delivery failure"
        assert await app.state.websocket_manager.get_events_since() == []

        event.listen(databases[0].sync_engine, "before_cursor_execute", deny_sql)
        try:
            await manager._notify_recording_failed("stream_72", "not published")
            await manager._record_failure_in_database(
                "stream_72", "not persisted", "test"
            )
        finally:
            event.remove(databases[0].sync_engine, "before_cursor_execute", deny_sql)
        assert observed and get_ident() not in observed
        assert len(attempted) == 1
        for index, database in enumerate(databases):

            def read():
                with database.sync_session_factory() as session:
                    return [
                        (row.id, row.status, row.error_message)
                        for row in session.scalars(select(Recording))
                    ]

            assert await run_in_thread_pool(read) == (
                [(11, "recording", None)] if index == 0 else []
            )
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        await close_owned(apps)


def seed_recording(database):
    with database.sync_session_factory() as session:
        session.add(Stream(id=72, streamer_id=1, title="own failure snapshot"))
        session.flush()
        session.add(
            Recording(
                id=11,
                stream_id=72,
                status="recording",
                start_time=datetime.now(timezone.utc),
            )
        )
        session.commit()
