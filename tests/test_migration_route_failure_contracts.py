"""Migration/refresh HTTP failures must not claim successful completion."""

from pathlib import Path

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,provider,operation,detail",
    [
        (
            "/api/migration/images",
            "get_image_migration_service",
            "migrate_all_images",
            "Migration failed",
        ),
        (
            "/api/migration/images/refresh",
            "get_image_refresh_service",
            "check_and_refresh_missing_images",
            "Image refresh failed",
        ),
        (
            "/api/migration/images/refresh/streamer/1",
            "get_image_refresh_service",
            "refresh_specific_streamer",
            "Failed to refresh streamer images",
        ),
        (
            "/api/migration/images/refresh/category/probe",
            "get_image_refresh_service",
            "refresh_specific_category",
            "Failed to refresh category image",
        ),
    ],
)
async def test_migration_service_fault_is_non_success_and_does_not_touch_peer(
    image_applications, monkeypatch, path, provider, operation, detail
):
    apps, databases, clients, _ = image_applications
    provider_function = getattr(dependencies, provider)
    service = provider_function(HTTPConnection({"type": "http", "app": apps[0]}))
    apps[0].dependency_overrides[provider_function] = lambda: service
    roots = [Path(app.state.settings.RECORDING_DIRECTORY) for app in apps]
    before = [
        {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*.jpg")}
        for root in roots
    ]

    async def unavailable(*_args, **_kwargs):
        raise OSError("synthetic-migration-service-fault")

    monkeypatch.setattr(service, operation, unavailable)
    response = await clients[0].post(path)
    assert response.status_code == 500 and detail in response.text
    assert "synthetic-migration-service-fault" not in response.text
    for index, root in enumerate(roots):
        assert {
            str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*.jpg")
        } == before[index]
        assert databases[index].sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_migration_status_inspection_fault_is_safe_and_retryable(
    image_applications, monkeypatch
):
    apps, _, clients, _ = image_applications
    service = dependencies.get_image_migration_service(
        HTTPConnection({"type": "http", "app": apps[0]})
    )
    native_exists = Path.exists
    inspected = []

    def unavailable(path):
        if path == service.old_images_dir:
            inspected.append(path)
            raise RuntimeError("synthetic-status-inspection-fault")
        return native_exists(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "exists", unavailable)
        response = await clients[0].get("/api/migration/images/status")
    assert inspected
    assert response.status_code == 500 and "Failed to check status" in response.text
    assert "synthetic-status-inspection-fault" not in response.text
    for client in clients:
        retry = await client.get("/api/migration/images/status")
        assert retry.status_code == 200
        assert retry.json()["migration_needed"] is False
