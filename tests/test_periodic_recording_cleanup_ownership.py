"""Periodic cleanup needs physical death, never age or global memory absence."""

import asyncio
import importlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from threading import get_ident
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy import inspect
from app.database import Base, DatabaseLifecycle
from app.models import Recording, Stream, Streamer
from app.services.recording.process_manager import ProcessManager
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest.mark.asyncio
async def test_periodic_cleanup_preserves_old_live_unknown_and_peer_catalogs(
    tmp_path, monkeypatch
):
    startup = importlib.import_module("app.services.init.startup_init")
    database_module = importlib.import_module("app.database")
    databases, recorders = [], []
    schemas = []
    queries = []
    loop_thread = get_ident()
    child = None
    try:
        for name in ("first", "second"):
            root = tmp_path / name
            root.mkdir()
            if postgres_url := os.environ.get("STREAMVAULT_PERIODIC_TEST_URL"):
                url = make_url(postgres_url)
                assert url.get_backend_name() == "postgresql" and url.host in {"127.0.0.1", "localhost", "::1"} and (url.database or "").startswith("streamvault_test_"), "periodic tests require local disposable PostgreSQL before any connection"
                schema = "periodic_" + uuid4().hex
                admin = create_engine(postgres_url)
                with admin.begin() as connection:
                    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                schemas.append((admin, schema))
                database = DatabaseLifecycle(
                    url.update_query_dict({"options": "-csearch_path=" + schema}).render_as_string(
                        hide_password=False
                    )
                )
            else:
                database = DatabaseLifecycle(f"sqlite:///{root / 'owned.db'}")
            databases.append(database)
            assert not inspect(database.sync_engine).get_table_names(), (
                "probe requires empty owned databases"
            )
            with database.sync_engine.begin() as connection:
                if database.sync_engine.dialect.name == "sqlite":
                    connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username="alice", twitch_id="alice"))
                session.flush()
                for recording_id, stream_id in ((7, 70), (8, 71)):
                    session.add(Stream(id=stream_id, streamer_id=1, title=name))
                    session.flush()
                    session.add(
                        Recording(
                            id=recording_id,
                            stream_id=stream_id,
                            status="recording",
                            start_time=datetime.now(timezone.utc) - timedelta(hours=2),
                        )
                    )
                session.commit()
            # Keep the original death/peer-DB assertions without importing #842's factory.
            processes = object.__new__(ProcessManager)
            processes.lock = asyncio.Lock()
            processes.active_processes = {}
            processes.long_stream_processes = {}
            processes.upstream_coordinator = TwitchUpstreamCoordinator(
                database.sync_session_factory, monotonic_clock=time.monotonic
            )
            memory = {}
            state = SimpleNamespace(
                get_active_recordings=lambda memory=memory: dict(memory),
                get_active_recording=memory.get,
                remove_active_recording=lambda rid, memory=memory: memory.pop(
                    rid, None
                ),
            )
            recorder = SimpleNamespace(
                process_manager=processes,
                orchestrator=SimpleNamespace(state_manager=state),
            )
            recorders.append(recorder)
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; print('ready', flush=True); time.sleep(60)",
            stdout=asyncio.subprocess.PIPE,
        )
        assert await asyncio.wait_for(child.stdout.readline(), 2) == b"ready\n"
        recorders[0].process_manager.active_processes["stream_70"] = child
        monkeypatch.setattr(startup, "get_recording_manager", lambda: recorders[0])
        monkeypatch.setattr(
            database_module, "SessionLocal", databases[0].sync_session_factory
        )
        assert await startup._cleanup_zombie_recordings_now() == 0
        assert queries and loop_thread not in queries
        for database in databases:
            with database.sync_session_factory() as session:
                assert [session.get(Recording, rid).status for rid in (7, 8)] == [
                    "recording",
                    "recording",
                ]
        child.terminate()
        await child.wait()
        queries.clear()
        assert (
            await startup._cleanup_zombie_recordings_now(recording_manager=recorders[0])
            == 1
        )
        assert (
            await startup._cleanup_zombie_recordings_now(recording_manager=recorders[0])
            == 0
        )
        assert queries and loop_thread not in queries
        with databases[0].sync_session_factory() as session:
            row = session.get(Recording, 7)
            assert row.status == "stopped" and row.end_time is not None
            assert row.duration >= 7200
            assert session.get(Recording, 8).status == "recording"
        with databases[1].sync_session_factory() as session:
            assert [session.get(Recording, rid).status for rid in (7, 8)] == [
                "recording",
                "recording",
            ]
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        if child is not None and child.returncode is None:
            child.kill()
            await child.wait()
        for recorder in recorders:
            recorder.process_manager.active_processes.pop("stream_70", None)
        for database in databases:
            await database.adispose()
        for admin, schema in schemas:
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin.dispose()
