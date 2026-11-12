"""Settings API fault mapping releases real SQL scopes and preserves retry/peer data."""

import pytest
from sqlalchemy import event

from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/settings/streamer"),
        ("get", "/api/settings/streamers"),
        ("post", "/api/settings/streamer/1"),
    ],
)
async def test_settings_catalog_failure_is_bounded_without_foreign_writes(
    image_applications, method, path
):
    _, databases, clients, _ = image_applications
    observed = []

    def unavailable(_connection, _cursor, statement, *_args):
        if "FROM streamers" in statement or "FROM notification_settings" in statement:
            observed.append(statement)
            raise OSError("synthetic-settings-query-fault")

    event.listen(databases[0].sync_engine, "before_cursor_execute", unavailable)
    try:
        response = await getattr(clients[0], method)(
            path, **({"json": {}} if method == "post" else {})
        )
    finally:
        event.remove(databases[0].sync_engine, "before_cursor_execute", unavailable)
    assert observed
    assert response.status_code == 500
    assert "synthetic-settings-query-fault" not in response.text
    assert databases[0].sync_engine.pool.checkedout() == 0
    if method == "get":
        assert (await clients[0].get(path)).status_code == 200
        assert (await clients[1].get(path)).status_code == 200


@pytest.mark.asyncio
async def test_websocket_diagnostic_failure_is_safe_http_error_and_peer_survives(
    image_applications, monkeypatch
):
    apps, _, clients, _ = image_applications

    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("synthetic-socket-delivery-fault")

    monkeypatch.setattr(
        apps[0].state.websocket_manager, "send_notification", unavailable
    )
    failed = await clients[0].post("/api/settings/test-websocket-notification")
    assert failed.status_code == 500 and "Internal server error" in failed.text
    assert "synthetic-socket-delivery-fault" not in failed.text
    peer = await clients[1].post("/api/settings/test-websocket-notification")
    assert peer.status_code == 200 and peer.json()["status"] == "success"
    assert peer.json()["notification_id"]
