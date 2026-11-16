"""Mounted image routes map real I/O and explicit service/scheduler faults safely."""

import os
from pathlib import Path

import pytest
from sqlalchemy import event
from starlette.background import BackgroundTasks
from starlette.requests import HTTPConnection

from app import dependencies
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("directory", ["profiles", "categories", "artwork/1"])
@pytest.mark.parametrize(
    "failure,expected_status", [(PermissionError, 404), (RuntimeError, 500)]
)
async def test_file_inspection_failure_is_bounded_and_does_not_change_peer(
    image_applications, monkeypatch, directory, failure, expected_status
):
    apps, _, clients, _ = image_applications
    root = Path(apps[0].state.settings.RECORDING_DIRECTORY)
    native_stat = os.stat
    observed = []

    def denied(path, *args, **kwargs):
        if (
            isinstance(path, (str, os.PathLike))
            and str(path).startswith(str(root))
            and Path(path).name == "probe.jpg"
        ):
            observed.append(str(path))
            raise failure("synthetic-private-file-marker")
        return native_stat(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "stat", denied)
        response = await clients[0].get(f"/data/images/{directory}/probe.jpg")
    assert observed
    assert response.status_code == expected_status
    assert (
        "Internal server error" if expected_status == 500 else "not found"
    ) in response.text
    assert "synthetic-private-file-marker" not in response.text
    peer = await clients[1].get(f"/data/images/{directory}/probe.jpg")
    assert peer.status_code == 200 and peer.content == b"owner-1"
    assert (
        await clients[0].get(f"/data/images/{directory}/probe.jpg")
    ).content == b"owner-0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/data/images/profile/1",
        "/api/images/streamer/1",
        "/api/images/streamers",
        "/api/images/streamer/1/download",
        "/api/images/categories",
    ],
)
async def test_catalog_fault_is_safe_500_releases_pool_and_can_retry(
    image_applications, path
):
    _, databases, clients, _ = image_applications

    def denied(_connection, _cursor, statement, *_args):
        if "FROM streamers" in statement or "FROM categories" in statement:
            raise OSError("synthetic-private-query-marker")

    event.listen(databases[0].sync_engine, "before_cursor_execute", denied)
    method = "post" if path.endswith("/download") else "get"
    try:
        response = await getattr(clients[0], method)(path)
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", denied)
    assert response.status_code == 500 and "Internal server error" in response.text
    assert "synthetic-private-query-marker" not in response.text
    assert databases[0].sync_engine.pool.checkedout() == 0
    if method == "get":
        assert (await clients[0].get(path)).status_code == 200
        assert (await clients[1].get(path)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,operation",
    [
        ("/data/images/stats", "get_stats"),
        ("/api/images/stats", "get_stats"),
        ("/data/images/category/probe", "get_category_image_url"),
        ("/api/images/category/probe", "get_category_image_url"),
    ],
)
async def test_service_failure_maps_to_safe_http_error(
    image_applications, monkeypatch, path, operation
):
    apps, _, clients, _ = image_applications
    service = dependencies.get_image_service(
        HTTPConnection({"type": "http", "app": apps[0]})
    )

    def unavailable(*_args, **_kwargs):
        raise OSError("synthetic-private-service-marker")

    monkeypatch.setattr(service, operation, unavailable)
    response = await clients[0].get(path)
    assert response.status_code == 500 and "Internal server error" in response.text
    assert "synthetic-private-service-marker" not in response.text
    assert (await clients[1].get(path)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/data/images/sync/profiles",
        "/data/images/sync/categories",
        "/data/images/cleanup",
        "/api/images/streamer/1/download",
        "/api/images/category/probe/download",
        "/api/images/sync",
        "/api/images/cleanup",
        "/api/images/sync/check-missing",
    ],
)
async def test_rejected_background_registration_never_claims_started(
    image_applications, monkeypatch, path
):
    _, databases, clients, _ = image_applications
    registrations = []

    def rejected(self, function, *args, **kwargs):
        registrations.append((function, args, kwargs))
        assert not self.tasks
        raise RuntimeError("synthetic-private-registration-marker")

    monkeypatch.setattr(BackgroundTasks, "add_task", rejected)
    response = await clients[0].post(path)
    assert registrations
    assert response.status_code == 500 and "Internal server error" in response.text
    assert (
        "started" not in response.text
        and "synthetic-private-registration-marker" not in response.text
    )
    assert databases[0].sync_engine.pool.checkedout() == 0
