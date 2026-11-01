"""Durable recording state returns closed immutable values, not ORM identities."""

import os
from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event, inspect

from app.database import Base, DatabaseLifecycle
from app.models import ActiveRecordingState, Recording, Stream, Streamer
from app.services.core.state_persistence_service import StatePersistenceService


@pytest.mark.asyncio
async def test_state_persistence_owns_sessions_values_recovery_io_and_heartbeat(
    tmp_path, monkeypatch
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    services = []
    queries = []
    probes = []
    loop_thread = get_ident()
    native_stat = os.stat
    paths = [tmp_path / (name + ".ts") for name in ("first", "second")]
    for path in paths:
        path.write_bytes(b"owned recording fixture")

    def stat(candidate, *args, **kwargs):
        if isinstance(candidate, (str, os.PathLike)) and Path(candidate) in paths:
            probes.append(get_ident())
        return native_stat(candidate, *args, **kwargs)

    try:
        for index, database in enumerate(databases):
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username=str(index), twitch_id=str(index)))
                session.flush()
                session.add(Stream(id=1, streamer_id=1))
                session.flush()
                session.add(
                    Recording(
                        id=1,
                        stream_id=1,
                        status="recording",
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            services.append(
                StatePersistenceService(
                    session_factory=lambda database=database: (
                        database.sync_session_factory()
                    )
                )
            )
        assert queries == []
        for index, (service, path, database) in enumerate(
            zip(services, paths, databases, strict=True)
        ):
            native_process_exists = service._process_exists

            def process_exists(pid, native=native_process_exists):
                probes.append(get_ident())
                return native(pid)

            monkeypatch.setattr(service, "_process_exists", process_exists)
            value = await service.save_active_recording(
                1,
                1,
                os.getpid(),
                "probe",
                str(index),
                datetime.now(timezone.utc),
                str(path),
                config={"nested": {"codec": "h264"}},
            )
            assert {field.name for field in fields(value)} == set(
                ActiveRecordingState.__table__.columns.keys()
            )
            assert inspect(value, raiseerr=False) is None
            with pytest.raises(FrozenInstanceError):
                value.streamer_name = "changed"
            assert value.get_config() == {"nested": {"codec": "h264"}}
            modified = value.get_config()
            modified["nested"]["codec"] = "changed"
            assert value.get_config() == {"nested": {"codec": "h264"}}
            assert value.streamer_name == str(index)
            assert database.sync_engine.pool.checkedout() == 0
            updated = await service.save_active_recording(
                1,
                1,
                os.getpid(),
                "probe",
                str(index),
                value.started_at,
                str(path),
                quality="720p",
            )
            assert updated.id == value.id and updated.created_at == value.created_at
            assert updated.quality == "720p" and updated.get_config() == {}
            assert value.quality == "best"
            assert await service.update_heartbeat(1)
            assert not await service.update_heartbeat(999)
            loaded = await service.load_state()
            assert len(loaded) == 1 and loaded[0].streamer_name == str(index)
            with monkeypatch.context() as watched:
                watched.setattr(os, "stat", stat)
                recovered = await service.recover_active_recordings()
            assert len(recovered) == 1 and recovered[0]["stream_id"] == 1
            assert recovered[0]["ts_output_path"] == str(path)
            assert await service._refresh_heartbeats_for_live_processes() == 1
            assert await service.cleanup_stale_entries() == 0
        assert probes and loop_thread not in probes
        assert queries and loop_thread not in queries
        await services[0].start()
        await services[1].start()
        await services[0].stop()
        assert services[0].heartbeat_task.done()
        assert services[1].is_running and not services[1].heartbeat_task.done()
        assert await services[0].remove_active_recording(1)
        assert not await services[0].remove_active_recording(1)
        assert len(await services[1].get_all_active_recordings()) == 1
        assert await services[0].get_all_active_recordings() == []
        await services[1].stop()
        for database in databases:
            assert database.sync_engine.pool.checkedout() == 0
    finally:
        for service in services:
            await service.stop()
        for database in databases:
            await database.adispose()
