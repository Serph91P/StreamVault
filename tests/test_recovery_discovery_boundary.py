"""Discovery returns plain closed values and never borrows another app's catalog."""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event as ThreadEvent, get_ident

import pytest
from sqlalchemy import event, select
from starlette.requests import HTTPConnection

from app import dependencies
from app.config.settings import Settings
from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.models import Recording, RecordingProcessingState, Stream, Streamer
from app.services.recording.unified_recovery_service import (
    RecoveryStats,
    UnifiedRecoveryService,
)
from app.utils.async_db_utils import run_in_thread_pool


def snapshot(database):
    with database.sync_session_factory() as session:
        return {
            table.name: [tuple(row) for row in session.execute(select(table)).all()]
            for table in Base.metadata.sorted_tables
        }


def assert_plain(value):
    assert not isinstance(value, Base)
    if isinstance(value, dict):
        for item in value.values():
            assert_plain(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            assert_plain(item)


@pytest.mark.asyncio
@pytest.mark.parametrize("directory_name", ["recordings", "media"])
async def test_recovery_discovery_and_enqueue_use_only_owned_closed_worker_scopes(
    tmp_path, monkeypatch, directory_name
):
    databases = []
    recorders = []
    services = []
    applications = []
    queries = []
    probes = []
    before = []
    loop_thread = get_ident()
    native_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        for name in ("first", "second"):
            root = tmp_path / name / directory_name
            directory = root / "alice" / "Season 2026"
            directory.mkdir(parents=True)
            source = directory / "failed.ts"
            source.write_bytes(b"size-guard input, not a decoding fixture" * 100)
            (directory / "test_write_7.tmp").write_bytes(
                b"existing data must not be a write probe"
            )
            segments = directory / "orphaned_segments"
            segments.mkdir()
            (segments / "0001.ts").write_bytes(b"segment")
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
            databases.append(database)
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username="alice", twitch_id="alice"))
                session.flush()
                session.add(Stream(id=70, streamer_id=1, title=name))
                session.flush()
                session.add(
                    Recording(
                        id=7,
                        stream_id=70,
                        path=str(source),
                        status="completed",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            app = create_app(
                settings=Settings(
                    ENVIRONMENT="test", RECORDING_DIRECTORY=str(root), _env_file=None
                ),
                database=database,
            )
            applications.append(app)
            recorder = await run_in_thread_pool(
                dependencies.get_application_recording_manager,
                HTTPConnection({"type": "http", "app": app, "headers": []}),
            )
            recorders.append(recorder)
            services.append(
                UnifiedRecoveryService(
                    session_factory=database.sync_session_factory,
                    settings=app.state.settings,
                    recording_manager=recorder,
                    queue_service=app.state.background_queue_service,
                )
            )
            before.append(snapshot(database))
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            results = await asyncio.gather(
                *(
                    asyncio.gather(
                        service._scan_orphaned_segments(72),
                        service._scan_failed_post_processing(72),
                    )
                    for service in services
                )
            )
        assert queries and loop_thread not in queries
        assert probes and loop_thread not in probes
        for index, (orphans, failed) in enumerate(results):
            assert_plain(orphans)
            assert_plain(failed)
            assert len(orphans) == len(failed) == 1
            assert orphans[0]["recording_id"] is None
            assert failed[0]["recording_id"] == 7
            assert "recording" not in failed[0]
            assert str(failed[0]["ts_path"]).startswith(
                str(services[index].recordings_base_path)
            )
            assert databases[index].sync_engine.pool.checkedout() == 0
        operation_queries = len(queries)
        for index, database in enumerate(databases):
            assert snapshot(database) == before[index]
        queries[:] = queries[:operation_queries]
        probes.clear()
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            accepted = await asyncio.gather(
                *(
                    service._trigger_post_processing(
                        7, str(failed[0]["ts_path"]), "alice"
                    )
                    for service, (_, failed) in zip(services, results, strict=True)
                )
            )
        assert accepted == [True, True]
        assert loop_thread not in queries
        assert probes and loop_thread not in probes
        for app, database in zip(applications, databases, strict=True):

            def stored_tasks():
                with database.sync_session_factory() as session:
                    state = (
                        session.query(RecordingProcessingState)
                        .filter_by(recording_id=7)
                        .one()
                    )
                    ids = list(state.get_task_ids().values())
                return app.state.background_queue_service.queue_manager.task_store.snapshot(
                    ids
                )

            tasks = await run_in_thread_pool(stored_tasks)
            assert tasks and any(
                task.task_type == "mp4_remux" for task in tasks.values()
            )
            probe = (
                Path(app.state.settings.RECORDING_DIRECTORY)
                / "alice"
                / "Season 2026"
                / "test_write_7.tmp"
            )
            assert probe.read_bytes() == b"existing data must not be a write probe"
            assert database.sync_engine.pool.checkedout() == 0
        queries.clear()
        found = await asyncio.gather(
            *(
                service._find_recording_by_path(str(failed[0]["ts_path"]))
                for service, (_, failed) in zip(services, results, strict=True)
            )
        )
        peer_before = await run_in_thread_pool(snapshot, databases[1])
        output_path = str(
            services[0].recordings_base_path / "alice" / "concatenated.ts"
        )
        await services[0]._update_recording_after_concatenation(7, output_path)
        assert found == [7, 7]
        assert queries and loop_thread not in queries
        with databases[0].sync_session_factory() as session:
            updated = session.get(Recording, 7)
            assert updated.path == output_path
            assert updated.status == "completed" and updated.end_time is not None
        assert snapshot(databases[1]) == peer_before
        queries.clear()
        paths = [
            str(service.recordings_base_path / "alice" / "Season 2026" / "orphaned.ts")
            for service in services
        ]
        before_rejected = await asyncio.gather(
            *(run_in_thread_pool(snapshot, database) for database in databases)
        )
        rejected = await asyncio.gather(
            *(
                service._adopt_recording(candidate)
                for index, service in enumerate(services)
                for candidate in (
                    paths[1 - index],
                    str(service.recordings_base_path / "alice"),
                )
            )
        )
        assert rejected and all(identity is None for identity in rejected)
        assert (
            await asyncio.gather(
                *(run_in_thread_pool(snapshot, database) for database in databases)
            )
            == before_rejected
        )
        adopted = await asyncio.gather(
            *(
                service._adopt_recording(path)
                for service, path in zip(services, paths, strict=True)
            )
        )
        assert all(isinstance(identity, int) for identity in adopted)
        assert queries and loop_thread not in queries
        for database, identity, path in zip(databases, adopted, paths, strict=True):
            with database.sync_session_factory() as session:
                created = session.get(Recording, identity)
                assert created.path == path and created.status == "stopped"
                assert created.stream_id != 70
            assert database.sync_engine.pool.checkedout() == 0
        with databases[0].sync_session_factory() as session:
            session.add(
                Recording(
                    id=17,
                    stream_id=70,
                    status="recording",
                    start_time=datetime.now(timezone.utc),
                )
            )
            session.commit()
        queries.clear()
        activity = await asyncio.gather(
            *(service._check_if_stream_has_active_recording(7) for service in services)
        )
        assert activity == [True, False]
        assert queries and loop_thread not in queries
        for database in databases:
            with database.sync_session_factory() as session:
                session.add(
                    Recording(
                        id=27,
                        stream_id=70,
                        status="recording",
                        start_time=datetime.now(timezone.utc) - timedelta(days=30),
                    )
                )
                session.commit()
        queries.clear()
        stats = [RecoveryStats(), RecoveryStats()]
        await asyncio.gather(
            *(
                service._final_database_cleanup(statistics)
                for service, statistics in zip(services, stats, strict=True)
            )
        )
        assert queries and loop_thread not in queries
        assert [statistics.updated_database_entries for statistics in stats] == [0, 0]
        for database in databases:
            with database.sync_session_factory() as session:
                assert session.get(Recording, 27) is not None
        dead_child = await asyncio.create_subprocess_exec("python", "-c", "pass")
        await dead_child.wait()
        recorders[1].process_manager.active_processes["stream_70"] = dead_child
        await services[1]._final_database_cleanup(stats[1])
        assert stats[1].updated_database_entries == 1
        with databases[1].sync_session_factory() as session:
            assert session.get(Recording, 27) is None
        with databases[0].sync_session_factory() as session:
            assert session.get(Recording, 27) is not None
        started, release = ThreadEvent(), ThreadEvent()

        def held_maintenance(session):
            row = session.get(Recording, 7)
            row.duration = 43
            session.flush()
            started.set()
            assert release.wait(5)
            return 43

        maintenance = asyncio.create_task(
            recorders[1].process_manager.upstream_coordinator.run_capture_maintenance(
                held_maintenance
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 5)
            maintenance.cancel()
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not maintenance.done()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await maintenance
            assert databases[1].sync_engine.pool.checkedout() == 0
            with databases[1].sync_session_factory() as session:
                assert session.get(Recording, 7).duration == 43
        finally:
            release.set()
            await asyncio.gather(maintenance, return_exceptions=True)

            async def wait_closed():
                while databases[1].sync_engine.pool.checkedout():
                    await asyncio.sleep(0.001)

            await asyncio.wait_for(wait_closed(), 5)
        for database in databases:
            assert database.sync_engine.pool.checkedout() == 0
    finally:
        for app in applications:
            await app.state.background_queue_manager.shutdown()
            await app.state.websocket_manager.close_all()
        for recorder in recorders:
            await recorder.shutdown()
        for database in databases:
            await database.adispose()


@pytest.mark.parametrize(
    "resource", ["session_factory", "settings", "recording_manager", "queue_service"]
)
def test_recovery_rejects_partial_application_context(resource):
    with pytest.raises(ValueError, match="together"):
        UnifiedRecoveryService(**{resource: object()})
