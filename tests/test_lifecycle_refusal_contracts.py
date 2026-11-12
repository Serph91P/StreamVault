"""Native lifecycle refusal/fault boundaries: no unowned provider launch or receipt.

Value: protects=failed start never admits child/external task and preserves peer;
fails_when=missing owner, catalog race or native output failure admits recording;
why_new=positive child/start table does not cover pre-start deletion/root denial;
seam=none; no_claim=provider capture, media success or positive process admission.
"""

from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.retry_decorator import NonRetryableError
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "force-missing-streamer",
        "catalog-denied",
        "stream-removed-before-path",
        "output-denied",
    ],
)
async def test_recording_start_refusal_has_native_owned_terminal_effects(
    image_applications, monkeypatch, case
):
    apps, databases, _clients, _ = image_applications
    app, database = apps[0], databases[0]
    app.state.settings.TWITCH_OAUTH_TOKEN = ""
    root = Path(app.state.settings.RECORDING_DIRECTORY)

    def seed():
        for index, owner in enumerate(databases):
            with owner.sync_session_factory() as db:
                db.add(Stream(id=70, streamer_id=1, title="native refusal"))
                db.flush()
                if index == 1:
                    db.add(
                        Recording(
                            id=7,
                            stream_id=70,
                            status="stopped",
                            start_time=datetime.now(timezone.utc),
                        )
                    )
                db.commit()

    await run_in_thread_pool(seed)
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    lifecycle = manager.orchestrator.lifecycle_manager
    attempted = []

    async def forbidden_provider(*args, **kwargs):
        attempted.append((args, kwargs))
        raise AssertionError("Refused start must not reach an external provider")

    monkeypatch.setattr(
        lifecycle.process_manager,
        "_start_segment" if case == "output-denied" else "start_recording_process",
        forbidden_provider,
    )
    native_get = lifecycle.database_service.get_stream_by_id
    reads = []
    if case == "stream-removed-before-path":

        async def removed_after_read(identity):
            result = await native_get(identity)
            if result is not None and not reads:
                reads.append(identity)

                def remove():
                    with database.sync_session_factory() as db:
                        db.delete(db.get(Stream, identity))
                        db.commit()

                await run_in_thread_pool(remove)
            return result

        monkeypatch.setattr(
            lifecycle.database_service, "get_stream_by_id", removed_after_read
        )
    native_mkdir = Path.mkdir
    probes = []

    def denied_mkdir(path, *args, **kwargs):
        if str(path).startswith(str(root)):
            probes.append(get_ident())
            raise PermissionError("synthetic-own-recording-mkdir-denied")
        return native_mkdir(path, *args, **kwargs)

    queries, listeners = [], []
    for index, owner in enumerate(databases):

        def observe(*_args, index=index):
            queries.append((index, get_ident()))
            if index == 0 and case == "catalog-denied":
                raise NonRetryableError("synthetic-owned-start-catalog-denial")

        event.listen(owner.sync_engine, "before_cursor_execute", observe)
        listeners.append(observe)
    try:
        with monkeypatch.context() as scoped:
            if case == "output-denied":
                # Existing roots permit a legitimate fallback; make the owned
                # root actually unavailable before refusing its recreation.
                root.rename(root.with_name(root.name + "-temporarily-moved"))
                scoped.setattr(Path, "mkdir", denied_mkdir)
            if case == "force-missing-streamer":
                result = await lifecycle.force_start_recording(999)
            else:
                result = await manager.orchestrator.start_recording(70, 1)
        assert result is None
        assert attempted == []
        assert not lifecycle.state_manager.get_active_recordings()
        assert all(
            not item.state.background_queue_service.external_tasks for item in apps
        )
        assert queries and {owner for owner, _thread in queries} == {0}
        assert get_ident() not in {thread for _owner, thread in queries}
        if case == "output-denied":
            assert probes and get_ident() not in probes
        assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
    finally:
        for owner, listener in zip(databases, listeners, strict=True):
            event.remove(owner.sync_engine, "before_cursor_execute", listener)
        await close_owned(apps)
    with databases[1].sync_session_factory() as db:
        assert db.query(Stream).count() == 1
        peer = db.query(Recording).one()
        assert peer.id == 7 and peer.status == "stopped" and peer.end_time is None
    with database.sync_session_factory() as db:
        rows = db.query(Recording).all()
        if case in {"output-denied", "stream-removed-before-path"}:
            assert len(rows) == 1 and rows[0].status == "failed"
            assert str(rows[0].path).startswith(str(root))
        else:
            assert rows == []
    assert all(owner.sync_engine.pool.checkedout() == 0 for owner in databases)
