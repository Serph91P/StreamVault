"""The log API operates off-loop and cannot borrow another app's log files."""

import builtins
import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from importlib import import_module
from inspect import iscoroutinefunction
import os
from pathlib import Path
from threading import get_ident

import pytest

from app.utils.async_db_utils import run_in_thread_pool
from app.lifespan import _close_application_logging
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.fixture
async def logging_applications(image_applications, tmp_path, monkeypatch):
    apps, databases, clients, _ = image_applications
    roots = [tmp_path / f"logs-{index}" for index in range(2)]
    contents = [f"owner-{index}\nsecond line\n" for index in range(2)]
    for app, root, content in zip(apps, roots, contents, strict=True):
        app.state.settings.LOGS_BASE_DIR = str(root)
        (root / "app").mkdir(parents=True)
        (root / "app" / "owned.log").write_text(content)
    observed = []
    native_stat = Path.stat
    native_unlink = Path.unlink
    native_open = builtins.open

    def stat(path, *args, **kwargs):
        if any(path.is_relative_to(root) for root in roots):
            observed.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)

    def unlink(path, *args, **kwargs):
        if any(path.is_relative_to(root) for root in roots):
            observed.append(get_ident())
        return native_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)

    def open_file(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and any(
            Path(path).is_relative_to(root) for root in roots
        ):
            observed.append(get_ident())
        return native_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", open_file)
    try:
        yield apps, databases, clients, roots, contents, observed
    finally:
        for app in apps:
            actor = getattr(app.state, "logging_service", None)
            if actor is not None:
                await run_in_thread_pool(actor.close)


@pytest.mark.parametrize(
    "name",
    [
        "list_log_files",
        "download_log_file",
        "tail_log_file",
        "delete_log_file",
        "cleanup_old_logs",
        "get_logging_stats",
    ],
)
def test_log_files_use_native_dispatch(name):
    assert not iscoroutinefunction(getattr(import_module("app.routes.logging"), name))


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["list", "stats", "download", "tail"])
async def test_real_log_reads_are_owned_and_off_loop(logging_applications, operation):
    _, _, clients, _, contents, observed = logging_applications
    for index, client in enumerate(clients):
        observed.clear()
        path = {
            "list": "/files",
            "stats": "/stats",
            "download": "/files/app/owned.log",
            "tail": "/files/app/owned.log/tail?lines=1",
        }[operation]
        response = await client.get("/logging" + path)
        assert response.status_code == 200, response.text
        if operation == "list":
            assert any(
                row["filename"] == "owned.log" for row in response.json()["app_logs"]
            )
        elif operation == "stats":
            assert response.json()["app"]["count"] >= 1
            assert response.json()["app"]["total_size"] >= len(contents[index].encode())
        elif operation == "download":
            assert response.content == contents[index].encode()
        else:
            assert response.json()["content"] == "second line\n"
            assert response.json()["total_lines"] == 2
        assert observed and get_ident() not in observed


@pytest.mark.asyncio
async def test_log_delete_has_only_the_owned_effect(logging_applications):
    _, _, clients, roots, _, observed = logging_applications
    for client in clients:
        assert (await client.get("/logging/files")).status_code == 200
    observed.clear()
    response = await clients[0].delete("/logging/files/app/owned.log")
    assert response.status_code == 200
    assert observed and get_ident() not in observed
    assert not (roots[0] / "app" / "owned.log").exists()
    assert (roots[1] / "app" / "owned.log").exists()


@pytest.mark.asyncio
async def test_log_cleanup_has_only_the_owned_effect(logging_applications):
    _, _, clients, roots, _, observed = logging_applications
    for client in clients:
        assert (await client.get("/logging/files")).status_code == 200
    files = [root / "app" / "expired.log" for root in roots]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    for path in files:
        path.write_text("synthetic expired log")
        os.utime(path, (old, old))
    observed.clear()
    cleanup = await clients[0].post("/logging/cleanup?days_to_keep=30")
    assert cleanup.status_code == 200, cleanup.text
    assert observed and get_ident() not in observed
    assert not files[0].exists()
    assert files[1].exists()


@pytest.mark.asyncio
async def test_owned_component_loggers_and_close_do_not_touch_the_peer(
    logging_applications,
):
    apps, _, clients, roots, _, _ = logging_applications
    for client in clients:
        assert (await client.get("/logging/files")).status_code == 200
    assert all(getattr(app.state, "logging_service", None) is not None for app in apps)
    first, peer = [app.state.logging_service for app in apps]
    assert first is not peer
    await run_in_thread_pool(first.log_recording_activity, "PROBE", "owner-zero-only")
    assert "owner-zero-only" in (roots[0] / "app" / "recording.log").read_text()
    assert "owner-zero-only" not in (roots[1] / "app" / "recording.log").read_text()
    streams = [
        handler.stream
        for actor in (first, peer)
        for logger in (
            actor.streamlink_logger,
            actor.ffmpeg_logger,
            actor.recording_logger,
        )
        for handler in logger.handlers
    ]
    await _close_application_logging(apps[0])
    assert apps[0].state.logging_service is None
    assert all(stream.closed for stream in streams[:3])
    assert all(not stream.closed for stream in streams[3:])
    await run_in_thread_pool(peer.log_recording_activity, "PROBE", "peer-remains-live")
    assert "peer-remains-live" in (roots[1] / "app" / "recording.log").read_text()


@pytest.mark.asyncio
async def test_log_listing_initialization_does_not_delete_existing_logs(
    logging_applications,
):
    _, _, clients, roots, _, _ = logging_applications
    files = [root / "app" / "expired.log" for root in roots]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    for path in files:
        path.write_text("existing archived log")
        os.utime(path, (old, old))
    response = await clients[0].get("/logging/files")
    assert response.status_code == 200
    assert any(row["filename"] == "expired.log" for row in response.json()["app_logs"])
    assert all(path.exists() for path in files)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,suffix", [("GET", ""), ("GET", "/tail"), ("DELETE", "")]
)
async def test_log_file_actions_reject_peer_symlinks(
    logging_applications, method, suffix
):
    _, _, clients, roots, contents, _ = logging_applications
    link = roots[0] / "app" / "peer-link.log"
    link.symlink_to(roots[1] / "app" / "owned.log")
    response = await clients[0].request(
        method, "/logging/files/app/peer-link.log" + suffix
    )
    assert response.status_code == 400
    assert link.is_symlink()
    assert (roots[1] / "app" / "owned.log").read_text() == contents[1]


@pytest.mark.asyncio
async def test_log_cleanup_failure_is_not_reported_as_success(
    logging_applications, monkeypatch
):
    _, _, clients, roots, _, _ = logging_applications
    assert (await clients[0].get("/logging/files")).status_code == 200
    path = roots[0] / "app" / "expired.log"
    path.write_text("retryable archived log")
    old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    os.utime(path, (old, old))
    original = os.remove

    def unavailable(target, *args, **kwargs):
        if Path(target) == path:
            raise PermissionError("synthetic log deletion failure")
        return original(target, *args, **kwargs)

    with monkeypatch.context() as blocked:
        blocked.setattr(os, "remove", unavailable)
        response = await clients[0].post("/logging/cleanup?days_to_keep=30")
        assert response.status_code == 500
        assert path.read_text() == "retryable archived log"
    retry = await clients[0].post("/logging/cleanup?days_to_keep=30")
    assert retry.status_code == 200
    assert not path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["files", "stats"])
async def test_log_listing_and_stats_do_not_follow_peer_symlinks(
    logging_applications, operation
):
    _, _, clients, roots, _, _ = logging_applications
    (roots[0] / "app" / "peer-link.log").symlink_to(roots[1] / "app" / "owned.log")
    response = await clients[0].get("/logging/" + operation)
    assert response.status_code == 200
    if operation == "files":
        assert "peer-link.log" not in [
            row["filename"] for row in response.json()["app_logs"]
        ]
    else:
        expected = sum(
            path.is_file() and not path.is_symlink()
            for path in (roots[0] / "app").glob("*.log*")
        )
        assert response.json()["app"]["count"] == expected


@pytest.mark.asyncio
async def test_owned_periodic_log_cleanup_stays_native_and_preserves_peer(
    logging_applications, monkeypatch
):
    apps, _, clients, roots, _, observed = logging_applications
    assert (await clients[0].get("/logging/files")).status_code == 200
    files = [root / "app" / "expired.log" for root in roots]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    for path in files:
        path.write_text("periodic archived log")
        os.utime(path, (old, old))
    cycles = 0

    async def one_cycle(delay):
        nonlocal cycles
        assert delay == 24 * 3600
        cycles += 1
        if cycles == 2:
            raise asyncio.CancelledError

    module = importlib.import_module("app.services.system.logging_service")
    observed.clear()
    with monkeypatch.context() as clock:
        clock.setattr(module.asyncio, "sleep", one_cycle)
        with pytest.raises(asyncio.CancelledError):
            await apps[0].state.logging_service._schedule_cleanup()
    assert observed and get_ident() not in observed
    assert not files[0].exists()
    assert files[1].exists()


@pytest.mark.asyncio
async def test_partial_log_initialization_closes_created_handlers_and_keeps_peer(
    logging_applications, monkeypatch
):
    apps, _, clients, _, contents, _ = logging_applications
    assert (await clients[1].get("/logging/files")).status_code == 200
    module = importlib.import_module("app.services.system.logging_service")
    constructor = module.TimedRotatingFileHandler
    created_streams = []
    calls = 0

    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError("synthetic component log initialization failure")
        handler = constructor(*args, **kwargs)
        created_streams.append(handler.stream)
        return handler

    with monkeypatch.context() as broken:
        broken.setattr(module, "TimedRotatingFileHandler", fail_second)
        response = await clients[0].get("/logging/files")
        assert response.is_server_error
        assert apps[0].state.logging_service is None
        assert created_streams and all(stream.closed for stream in created_streams)
    assert (await clients[1].get("/logging/files/app/owned.log")).content == contents[
        1
    ].encode()
    assert (await clients[0].get("/logging/files")).status_code == 200
