"""Settings mutations keep their whole SQL scope native and side effects app-owned."""

import importlib
from pathlib import Path
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import get_streamlink_config_service
from app.models import GlobalSettings

import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.mark.asyncio
async def test_settings_write_failure_rolls_back_only_own_scope(image_applications):
    from sqlalchemy import event

    _, databases, clients, _ = image_applications
    before = (await clients[0].get("/api/settings")).json()
    peer_before = (await clients[1].get("/api/settings")).json()
    observed = []

    def unavailable(_connection, _cursor, statement, *_):
        if statement.lstrip().startswith("UPDATE global_settings"):
            observed.append(get_ident())
            raise RuntimeError("synthetic settings write outage")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        response = await clients[0].post(
            "/api/settings", json={**before, "supported_codecs": "av1"}
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal server error"}
        assert observed and get_ident() not in observed
        assert (await clients[0].get("/api/settings")).json() == before
        assert (await clients[1].get("/api/settings")).json() == peer_before
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)


@pytest.mark.asyncio
async def test_settings_codec_save_regenerates_only_owned_config(
    image_applications, tmp_path, monkeypatch
):
    apps, databases, clients, queries = image_applications
    legacy = importlib.import_module(
        "app.services.system.streamlink_config_service"
    ).streamlink_config_service
    default_calls = []

    async def forbidden():
        default_calls.append(True)
        raise AssertionError("settings regenerated process-default Streamlink config")

    monkeypatch.setattr(legacy, "regenerate_config", forbidden)
    services = []
    for index, app in enumerate(apps):
        base = tmp_path / f"app-{index}"
        app.state.settings.BASE_DIR = str(base)
        (base / "config" / "streamlink").mkdir(parents=True)
        with databases[index].sync_session_factory() as db:
            db.add(GlobalSettings(id=1, supported_codecs="h264"))
            db.commit()
        service = get_streamlink_config_service(
            HTTPConnection({"type": "http", "app": app})
        )
        services.append(service)
        assert await service.regenerate_config()
    peer_before = Path(services[1].twitch_config_path).read_bytes()
    body = (await clients[0].get("/api/settings")).json()
    body["supported_codecs"] = "av1"
    queries.clear()
    response = await clients[0].post("/api/settings", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["supported_codecs"] == "av1"
    assert (
        "twitch-supported-codecs=av1"
        in Path(services[0].twitch_config_path).read_text()
    )
    assert Path(services[1].twitch_config_path).read_bytes() == peer_before
    assert not default_calls
    assert queries and get_ident() not in [thread for thread, _ in queries]
    assert (await clients[0].get("/api/settings")).json()["supported_codecs"] == "av1"
    assert (await clients[1].get("/api/settings")).json()["supported_codecs"] == "h264"
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,detail",
    [
        (
            "http_proxy",
            "ftp://synthetic.invalid",
            "HTTP proxy URL must start with 'http://' or 'https://'",
        ),
        (
            "https_proxy",
            "ftp://synthetic.invalid",
            "HTTPS proxy URL must start with 'http://' or 'https://'",
        ),
        (
            "notification_url",
            "synthetic-invalid-notification",
            "Invalid notification URL format",
        ),
    ],
)
async def test_invalid_settings_proxy_keeps_explicit_400_and_database_unchanged(
    image_applications,
    field,
    value,
    detail,
):
    _, databases, clients, _ = image_applications
    before = (await clients[0].get("/api/settings")).json()
    invalid = {**before, field: value}
    response = await clients[0].post("/api/settings", json=invalid)
    assert response.status_code == 400, response.text
    assert response.json() == {"detail": detail}
    assert (await clients[0].get("/api/settings")).json() == before
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
