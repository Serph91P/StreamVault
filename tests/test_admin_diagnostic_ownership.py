"""Mounted administration diagnostics use actual own paths off the event loop."""

import os
from datetime import datetime, timezone
from pathlib import Path
from threading import get_ident

import pytest

from app.models import Recording, Stream
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint", ["debug/recordings-directory", "debug/videos-database", "system/info"]
)
async def test_admin_filesystem_diagnostics_report_the_configured_owner_off_loop(
    image_applications, monkeypatch, endpoint
):
    apps, databases, clients, _ = image_applications
    roots = [Path(app.state.settings.RECORDING_DIRECTORY) for app in apps]
    for index, root in enumerate(roots):
        folder = root / ("own-channel" if index == 0 else "peer-channel") / "Season 1"
        folder.mkdir(parents=True)
        (folder / "fixture.mp4").write_bytes(b"a" * (100 if index == 0 else 900))
        (folder / "fixture.ts").write_bytes(b"own-ts")
        (folder / "fixture.json").write_text("{}")

    def seed():
        for index, database in enumerate(databases):
            path = (
                roots[index]
                / ("own-channel" if index == 0 else "peer-channel")
                / "Season 1"
                / "fixture.ts"
            )
            with database.sync_session_factory() as session:
                session.add(
                    Stream(
                        id=70,
                        streamer_id=1,
                        recording_path=str(path),
                        started_at=datetime.now(timezone.utc),
                    )
                )
                session.flush()
                session.add(
                    Recording(
                        id=7,
                        stream_id=70,
                        status="completed",
                        path=str(path),
                        start_time=datetime.now(timezone.utc),
                    )
                )
                session.commit()

    await run_in_thread_pool(seed)
    observed = []
    original_scan, original_vfs = os.scandir, os.statvfs

    def watch_scan(path="."):
        if isinstance(path, (str, os.PathLike)) and any(
            str(path).startswith(str(root)) for root in roots
        ):
            observed.append((str(path), get_ident()))
        return original_scan(path)

    def watch_vfs(path):
        if isinstance(path, (str, os.PathLike)) and any(
            str(path).startswith(str(root)) for root in roots
        ):
            observed.append((str(path), get_ident()))
        return original_vfs(path)

    monkeypatch.setattr(os, "scandir", watch_scan)
    monkeypatch.setattr(os, "statvfs", watch_vfs)
    response = await clients[0].get("/api/admin/" + endpoint)
    assert response.status_code == 200, response.text
    data = response.json()
    if endpoint == "debug/recordings-directory":
        data = data["data"]
        assert data["base_recordings_dir"] == str(roots[0])
        own = next(
            item for item in data["directories"] if item["name"] == "own-channel"
        )
        assert own["total_files"] == 3
        assert "peer-channel" not in response.text
    elif endpoint == "debug/videos-database":
        data = data["data"]
        assert data["summary"]["total_streams"] == 1
        assert data["recordings"][0]["mp4_path_size"] == 100
        assert data["filesystem_check"]["recordings_dir_exists"] is True
        names = [item["name"] for item in data["filesystem_check"]["subdirectories"]]
        assert "own-channel" in names and "peer-channel" not in names
    else:
        assert data["settings"]["recording_directory"] == str(roots[0])
        assert data["storage"]["recording_drive"]["free_gb"] >= 0
    assert observed and all(str(roots[0]) in path for path, _ in observed)
    assert get_ident() not in {thread for _, thread in observed}
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["status", "names", "all"])
async def test_admin_queue_status_and_cleanup_never_observe_or_mutate_peer_tasks(
    image_applications, monkeypatch, operation
):
    import importlib
    from app.services.background_queue_cleanup_service import (
        BackgroundQueueCleanupService,
    )

    apps, _, clients, _ = image_applications
    own, peer = (app.state.background_queue_service for app in apps)
    own.add_external_task("recording_7", "unknown", {"streamer_id": 1})
    for task_id in ("recording_7", "recording_8", "recording_9"):
        peer.add_external_task(task_id, "unknown", {"streamer_id": 1})
    route = importlib.import_module("app.routes.admin")
    legacy_cleanup = importlib.import_module(
        "app.services.background_queue_cleanup_service"
    )
    monkeypatch.setattr(route, "_background_queue_service", peer)
    monkeypatch.setattr(
        legacy_cleanup,
        "get_cleanup_service",
        lambda: BackgroundQueueCleanupService(peer),
    )
    try:
        if operation == "status":
            response = await clients[0].get("/api/admin/background-queue/status")
            assert response.status_code == 200 and response.json()["unknown_tasks"] == 1
        else:
            suffix = "task-names" if operation == "names" else "all"
            response = await clients[0].post(
                "/api/admin/background-queue/cleanup/" + suffix
            )
            assert response.status_code == 200
            assert all(
                task.task_type == "unknown" for task in peer.external_tasks.values()
            ), "Request A changed the peer/default B task objects"
            assert response.json()["task_names_fixed"] == 1
            assert own.external_tasks["recording_7"].task_type == "recording"
        assert len(peer.external_tasks) == 3
        assert all(task.task_type == "unknown" for task in peer.external_tasks.values())
    finally:
        await own.stop()
        await peer.stop()


@pytest.mark.asyncio
async def test_quick_health_probes_only_the_request_owner_in_worker(
    image_applications, monkeypatch
):
    import subprocess
    from sqlalchemy import event
    import app.database as database_module

    apps, databases, clients, _ = image_applications
    monkeypatch.setattr(
        database_module, "SessionLocal", databases[1].sync_session_factory
    )
    queries, commands, paths = [], [], []
    native_run, native_statvfs = subprocess.run, os.statvfs
    for index, database in enumerate(databases):
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_args, index=index: queries.append((index, get_ident())),
        )

    def run(command, *args, **kwargs):
        commands.append((command, get_ident()))
        return native_run(command, *args, **kwargs)

    def statvfs(path):
        paths.append((str(path), get_ident()))
        return native_statvfs(path)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(os, "statvfs", statvfs)
    response = await clients[0].post("/api/admin/tests/quick-health")
    assert response.status_code == 200, response.text
    checks = response.json()["checks"]
    assert checks["database"]["status"] == "healthy"
    assert checks["disk_space"]["status"] in {"healthy", "warning", "error"}
    assert queries and {owner for owner, _thread in queries} == {0}
    assert commands and [command for command, _thread in commands] == [
        ["ffmpeg", "-version"],
        ["streamlink", "--version"],
    ]
    assert [path for path, _thread in paths] == [
        apps[0].state.settings.RECORDING_DIRECTORY
    ]
    assert get_ident() not in {thread for _value, thread in queries + commands + paths}
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "database",
        "ffmpeg-failed",
        "ffmpeg-missing",
        "streamlink-failed",
        "streamlink-missing",
        "disk_space",
    ],
)
async def test_quick_health_reports_native_probe_failures_without_exception_details(
    image_applications, monkeypatch, failure
):
    import subprocess
    import sys
    from sqlalchemy import event

    apps, databases, clients, _ = image_applications
    native_run, native_statvfs = subprocess.run, os.statvfs
    faults = []
    sensitive_detail = "synthetic-private-probe-detail"

    def sql(_connection, _cursor, statement, *_args):
        if failure == "database" and statement.strip().upper() == "SELECT 1":
            faults.append(get_ident())
            raise PermissionError(sensitive_detail)

    event.listen(databases[0].sync_engine, "before_cursor_execute", sql)

    def run(command, *args, **kwargs):
        if failure.startswith(command[0] + "-"):
            faults.append(get_ident())
            if failure.endswith("missing"):
                raise FileNotFoundError(sensitive_detail)
            # Controlled child exit at the CLI port; other probes stay native.
            return native_run(
                [sys.executable, "-c", "raise SystemExit(17)"], *args, **kwargs
            )
        return native_run(command, *args, **kwargs)

    def statvfs(path):
        assert str(path) == apps[0].state.settings.RECORDING_DIRECTORY
        if failure == "disk_space":
            faults.append(get_ident())
            raise PermissionError(sensitive_detail)
        return native_statvfs(path)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(os, "statvfs", statvfs)
    try:
        response = await clients[0].post("/api/admin/tests/quick-health")
        assert response.status_code == 200, response.text
        data = response.json()
        target = failure.split("-")[0]
        assert data["checks"][target]["status"] == "error"
        assert data["overall_status"] != "healthy"
        assert sensitive_detail not in response.text
        assert datetime.fromisoformat(data["timestamp"])
        assert len(faults) == 1 and get_ident() not in faults
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", sql)


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_failure", [False, True])
async def test_mounted_recording_diagnostics_apply_native_fallbacks_without_peer_reads(
    image_applications, monkeypatch, catalog_failure
):
    from sqlalchemy import event

    apps, databases, clients, _ = image_applications
    roots = [Path(app.state.settings.RECORDING_DIRECTORY) for app in apps]
    paths = {}
    for index, root in enumerate(roots):
        for stream_id in range(70, 79):
            path = root / f"stream-{stream_id}.ts"
            path.write_bytes(bytes([stream_id]) * (stream_id if index == 0 else 900))
            paths[index, stream_id] = path
        (root / "stream-71.mp4").write_bytes(b"mp4" * (100 if index == 0 else 200))
    directory = roots[0] / "a-directory-not-a-file"
    directory.mkdir()

    def seed():
        for index, database in enumerate(databases):
            with database.sync_session_factory() as db:
                for stream_id in range(70, 79):
                    direct = (
                        str(paths[index, stream_id])
                        if index or stream_id in {70, 77}
                        else None
                    )
                    if index == 0 and stream_id == 75:
                        direct = str(directory)
                    db.add(
                        Stream(
                            id=stream_id,
                            streamer_id=1,
                            title=f"owner-{index}",
                            recording_path=direct,
                        )
                    )
                db.flush()
                for stream_id in range(71, 79):
                    stored = str(paths[index, stream_id])
                    if index == 0 and stream_id == 74:
                        stored += ".missing"
                    if index == 0 and stream_id == 76:
                        stored = None
                    if index == 0 and stream_id == 77:
                        stored = str(paths[0, 72])
                    db.add(
                        Recording(
                            id=stream_id,
                            stream_id=stream_id,
                            status="recording" if stream_id == 73 else "completed",
                            path=stored,
                            start_time=datetime.now(timezone.utc),
                        )
                    )
                db.commit()

    await run_in_thread_pool(seed)
    queries, probes, faults = [], [], []
    native_stat = os.stat
    denied = {str(paths[0, 77]): 3, str(paths[0, 78]): 2}
    stat_counts = {}

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and any(
            str(path).startswith(str(root)) for root in roots
        ):
            probes.append((str(path), get_ident()))
            if str(path) in denied:
                stat_counts[str(path)] = stat_counts.get(str(path), 0) + 1
                # Fail size retrieval after native exists/is_file succeeded;
                # Python 3.14 existence predicates suppress OSError themselves.
                if stat_counts[str(path)] >= denied[str(path)]:
                    faults.append(str(path))
                    raise PermissionError("synthetic-private-diagnostic-file-detail")
        return native_stat(path, *args, **kwargs)

    def sql(_connection, _cursor, statement, *_args, index):
        queries.append((index, get_ident()))
        if catalog_failure and "FROM streams" in statement:
            faults.append("catalog")
            raise PermissionError("synthetic-private-diagnostic-catalog-detail")

    listeners = []
    for index, database in enumerate(databases):

        def listener(*args, index=index):
            return sql(*args, index=index)

        event.listen(database.sync_engine, "before_cursor_execute", listener)
        listeners.append(listener)
    monkeypatch.setattr(os, "stat", stat)
    try:
        response = await clients[0].post(
            "/api/admin/debug/check-stream-recordings", json=list(range(70, 79)) + [999]
        )
        assert queries and {index for index, _thread in queries} == {0}
        assert get_ident() not in {thread for _index, thread in queries}
        assert "synthetic-private-diagnostic" not in response.text
        if catalog_failure:
            assert response.status_code == 500
            assert response.json()["detail"] == "Stream recording check failed"
            assert faults == ["catalog"]
        else:
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert {key: value["method"] for key, value in data.items()} == {
                "70": "stream_recording_path",
                "71": "recording_mp4_file",
                "72": "recording_ts_file",
                "73": "none",
                "74": "none",
                "75": "recording_ts_file",
                "76": "none",
                "77": "recording_ts_file",
                "78": "none",
                "999": "stream_not_found",
            }
            for stream_id, size in [(70, 70), (71, 300), (72, 72), (75, 75), (77, 72)]:
                assert data[str(stream_id)]["has_recording"] is True
                assert data[str(stream_id)]["file_size"] == size
                assert str(roots[0]) in data[str(stream_id)]["file_path"]
            for stream_id in [73, 74, 76, 78, 999]:
                assert data[str(stream_id)]["has_recording"] is False
            assert set(faults) == set(denied)
            assert probes and all(str(roots[0]) in path for path, _thread in probes)
            assert get_ident() not in {thread for _path, thread in probes}
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        for database, listener in zip(databases, listeners, strict=True):
            event.remove(database.sync_engine, "before_cursor_execute", listener)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layout,level",
    [("root", "INFO"), ("app", "ALL"), ("root", ""), ("missing", "INFO")],
)
async def test_recent_logs_tail_and_filter_only_the_configured_owner_off_loop(
    image_applications, monkeypatch, layout, level
):
    import subprocess

    apps, _databases, clients, _ = image_applications
    roots = [Path(app.state.settings.RECORDING_DIRECTORY) / "logs" for app in apps]
    for index, (app, root) in enumerate(zip(apps, roots, strict=True)):
        root.mkdir()
        monkeypatch.setattr(app.state.settings, "LOGS_BASE_DIR", str(root))
        target = root / ("app/app.log" if layout == "app" else "app.log")
        if layout != "missing" or index:
            target.parent.mkdir(exist_ok=True)
            target.write_text(
                f"INFO owner-{index} old\nERROR owner-{index} failure\nINFO owner-{index} latest\nDEBUG owner-{index} detail\n"
            )
    expected_path = roots[0] / ("app/app.log" if layout == "app" else "app.log")
    native_exists, native_run = Path.exists, subprocess.run
    probes, commands, forbidden = [], [], []

    def exists(path):
        if str(path) in {"/app/logs/app.log", "logs/app/app.log", "app.log"}:
            # Never read unrelated default logs even on the pre-fix RED path.
            forbidden.append(str(path))
            return False
        if str(path).startswith(str(roots[0])):
            probes.append(get_ident())
        return native_exists(path)

    def run(command, *args, **kwargs):
        commands.append((command, kwargs["timeout"], get_ident()))
        return native_run(command, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(subprocess, "run", run)
    response = await clients[0].get(
        "/api/admin/logs/recent", params={"lines": 3, "level": level}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    expected = ["ERROR owner-0 failure", "INFO owner-0 latest", "DEBUG owner-0 detail"]
    if level == "INFO":
        expected = ["INFO owner-0 latest"]
    if layout == "missing":
        expected = []
    assert data == {
        "log_file": None if layout == "missing" else str(expected_path),
        "lines_requested": 3,
        "lines_returned": len(expected),
        "level_filter": level,
        "logs": expected,
    }
    assert forbidden == []
    assert probes and get_ident() not in probes
    if layout == "missing":
        assert commands == []
    else:
        assert len(commands) == 1
        assert commands[0][:2] == (["tail", "-n", "3", str(expected_path)], 10)
        assert commands[0][2] != get_ident()
    assert "owner-1" not in response.text
