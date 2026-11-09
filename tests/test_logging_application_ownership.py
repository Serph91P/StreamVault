"""The log API operates off-loop and cannot borrow another app's log files."""

from datetime import datetime, timedelta, timezone
from importlib import import_module
from inspect import iscoroutinefunction
import os
from pathlib import Path
from threading import get_ident

import pytest

from app.utils.async_db_utils import run_in_thread_pool
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

    def stat(path, *args, **kwargs):
        if any(path.is_relative_to(root) for root in roots):
            observed.append(get_ident())
        return native_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
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
        response = await client.get("/api/logging" + path)
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
async def test_log_delete_and_cleanup_have_only_the_owned_effect(logging_applications):
    _, _, clients, roots, _, observed = logging_applications
    for client in clients:
        assert (await client.get("/api/logging/files")).status_code == 200
    observed.clear()
    response = await clients[0].delete("/api/logging/files/app/owned.log")
    assert response.status_code == 200
    assert observed and get_ident() not in observed
    assert not (roots[0] / "app" / "owned.log").exists()
    assert (roots[1] / "app" / "owned.log").exists()
    files = [root / "app" / "expired.log" for root in roots]
    old = (datetime.now(timezone.utc) - timedelta(days=45)).timestamp()
    for path in files:
        path.write_text("synthetic expired log")
        os.utime(path, (old, old))
    observed.clear()
    cleanup = await clients[0].post("/api/logging/cleanup?days_to_keep=30")
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
        assert (await client.get("/api/logging/files")).status_code == 200
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
    await run_in_thread_pool(first.close)
    assert all(stream.closed for stream in streams[:3])
    assert all(not stream.closed for stream in streams[3:])
    await run_in_thread_pool(peer.log_recording_activity, "PROBE", "peer-remains-live")
    assert "peer-remains-live" in (roots[1] / "app" / "recording.log").read_text()
