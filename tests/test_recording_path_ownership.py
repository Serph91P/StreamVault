"""Actual recording path generation must not borrow the default episode catalogue."""

import importlib
from datetime import datetime
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace

import pytest

from app.dependencies import _get_application_recording_manager
from app.lifespan import _close_application_proxy, _close_application_twitch
from app.models import Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_logging_application_ownership

image_applications = test_logging_application_ownership.image_applications
logging_applications = test_logging_application_ownership.logging_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,expected",
    [
        ("recordings", 8),
        ("oversized-path", 1),
        ("missing-column", 8),
        ("missing-streamer", 1),
        ("filesystem-error", 1),
        ("database-error", 1),
        ("legacy-settings", 7),
    ],
)
async def test_episode_compatibility_sources_close_scope(
    image_applications, monkeypatch, tmp_path, source, expected
):
    from sqlalchemy import event
    from app.models import Recording

    _, databases, _, queries = image_applications
    paths = importlib.import_module("app.utils.path_utils")
    now = datetime.now()
    prefix = f"S{now.year}{now.month:02d}E"

    def seed():
        with databases[0].sync_session_factory() as session:
            session.add(Stream(id=71, streamer_id=1, started_at=now))
            session.flush()
            if source in {"recordings", "missing-column", "oversized-path"}:
                suffix = "9" * 5000 if source == "oversized-path" else "07"
                session.add(
                    Recording(
                        id=72,
                        stream_id=71,
                        start_time=now,
                        status="completed",
                        path=f"/scope/{prefix}{suffix}-history.ts",
                    )
                )
            session.commit()

    await run_in_thread_pool(seed)
    touched = []
    sentinel = None

    def missing_column(_connection, _cursor, statement, *_):
        if statement.startswith("SELECT streams.episode_number"):
            touched.append(get_ident())
            raise RuntimeError("synthetic legacy episode column unavailable")

    if source == "missing-column":
        event.listen(databases[0].sync_engine, "before_cursor_execute", missing_column)
    if source in {"filesystem-error", "legacy-settings"}:
        directory = tmp_path / "owner-0" / f"Season {now.year}-{now.month:02d}"
        directory.mkdir(parents=True)
        sentinel = directory / f"{prefix}06-history.ts"
        sentinel.write_bytes(b"unchanged metadata sentinel")
        if source == "filesystem-error":
            original = paths.os.listdir

            def unavailable(path):
                if Path(path) == directory:
                    touched.append(get_ident())
                    raise PermissionError("synthetic episode directory unavailable")
                return original(path)

            monkeypatch.setattr(paths.os, "listdir", unavailable)
        else:
            configuration = importlib.import_module("app.config.settings")
            monkeypatch.setattr(
                configuration,
                "get_settings",
                lambda: SimpleNamespace(output_directory=str(tmp_path)),
            )
    factory = databases[0].sync_session_factory
    if source == "database-error":

        def unavailable_database():
            touched.append(get_ident())
            raise RuntimeError("synthetic episode database unavailable")

        factory = unavailable_database
    monkeypatch.setattr(paths, "SessionLocal", factory)
    queries.clear()
    try:
        value = await paths.get_episode_number(
            777 if source == "missing-streamer" else 1,
            now,
            recordings_directory=None if source == "legacy-settings" else str(tmp_path),
        )
        assert value == f"{expected:02d}"
        assert get_ident() not in [thread for thread, _ in queries]
        if source in {"missing-column", "filesystem-error", "database-error"}:
            assert touched and get_ident() not in touched
        else:
            assert queries
        assert databases[0].sync_engine.pool.checkedout() == 0
        if sentinel is not None:
            assert sentinel.read_bytes() == b"unchanged metadata sentinel"
    finally:
        if source == "missing-column":
            event.remove(
                databases[0].sync_engine, "before_cursor_execute", missing_column
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("template", ["default", "plex", "fallback"])
async def test_filename_sdk_preserves_preset_and_format_fallback(
    image_applications, tmp_path, template
):
    _, databases, _, _ = image_applications
    paths = importlib.import_module("app.utils.path_utils")
    actual_template = (
        "{unknown}_{year:02d}_{month:d}_{day:2d}_{episode:02d}_{streamer}"
        if template == "fallback"
        else template
    )
    now = datetime.now()
    value = await paths.generate_filename(
        SimpleNamespace(id=1, username="owner-0", twitch_id="synthetic"),
        {"title": "Hello", "category_name": "Category"},
        actual_template,
        session_factory=databases[0].sync_session_factory,
        recordings_directory=str(tmp_path),
    )
    assert value.endswith(".mp4") and "owner-0" in value
    if template == "plex":
        assert f"Season {now.year}-{now.month:02d}/" in value and "E01" in value
    elif template == "fallback":
        assert (
            value
            == f"{{unknown}}_{now.year:02d}_{now.month:d}_{now.day:2d}_1_owner-0.mp4"
        )
    else:
        assert "Hello_Category" in value
    assert databases[0].sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["path", "episode"])
async def test_legacy_path_sdk_updates_use_closed_native_scopes(
    image_applications, monkeypatch, operation
):
    _, databases, _, queries = image_applications
    paths = importlib.import_module("app.utils.path_utils")
    monkeypatch.setattr(paths, "SessionLocal", databases[0].sync_session_factory)

    def seed():
        with databases[0].sync_session_factory() as session:
            session.add(
                Stream(
                    id=71, streamer_id=1, started_at=datetime.now(), episode_number=3
                )
            )
            session.commit()

    await run_in_thread_pool(seed)
    queries.clear()
    if operation == "path":
        await paths.update_recording_path(71, "/scope/renamed.ts")
    else:
        await paths.update_episode_number(71, 4)
    assert queries and get_ident() not in [thread for thread, _ in queries]

    def stored():
        with databases[0].sync_session_factory() as session:
            row = session.get(Stream, 71)
            return row.recording_path, row.episode_number

    assert await run_in_thread_pool(stored) == (
        ("/scope/renamed.ts", 3) if operation == "path" else (None, 4)
    )
    assert databases[0].sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["catalogue", "filesystem"])
async def test_actual_recording_paths_use_owned_episode_history(
    logging_applications, image_applications, monkeypatch, source
):
    apps, databases, _, _, _, _ = logging_applications
    _, _, _, queries = image_applications
    now = datetime.now()
    old_episodes = (8, 3)
    sentinel_files = []
    default_calls = []
    paths = importlib.import_module("app.utils.path_utils")

    def forbid_default():
        default_calls.append(True)
        raise AssertionError("recording path borrowed the default catalogue")

    monkeypatch.setattr(paths, "SessionLocal", forbid_default)

    def seed(index):
        with databases[index].sync_session_factory() as session:
            session.add(
                Stream(
                    id=71,
                    streamer_id=1,
                    started_at=now,
                    episode_number=old_episodes[index]
                    if source == "catalogue"
                    else None,
                )
            )
            session.add(
                Stream(id=72, streamer_id=1, started_at=now, title=f"new-owner-{index}")
            )
            session.commit()
        if source == "filesystem":
            directory = (
                Path(apps[index].state.settings.RECORDING_DIRECTORY)
                / f"owner-{index}"
                / f"Season {now.year}-{now.month:02d}"
            )
            directory.mkdir(parents=True)
            file = (
                directory
                / f"owner-S{now.year}{now.month:02d}E{old_episodes[index]:02d}-preserved.ts"
            )
            file.write_bytes(b"synthetic filename-history sentinel")
            sentinel_files.append(file)

    def episode(index):
        with databases[index].sync_session_factory() as session:
            return session.get(Stream, 72).episode_number

    for index in range(2):
        await run_in_thread_pool(seed, index)
    try:
        managers = [
            await run_in_thread_pool(_get_application_recording_manager, app)
            for app in apps
        ]
        for index, manager in enumerate(managers):
            queries.clear()
            path = await manager._service.orchestrator.lifecycle_manager._generate_recording_path(
                1, 72
            )
            assert Path(path).is_relative_to(
                Path(apps[index].state.settings.RECORDING_DIRECTORY)
            )
            assert f"S{now.year}{now.month:02d}E{old_episodes[index] + 1:02d}" in path
            assert queries and get_ident() not in [thread for thread, _ in queries]
            assert await run_in_thread_pool(episode, index) == old_episodes[index] + 1
            if index == 0:
                assert await run_in_thread_pool(episode, 1) is None
        assert not default_calls
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
        for file in sentinel_files:
            assert file.read_bytes() == b"synthetic filename-history sentinel"
    finally:
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)
