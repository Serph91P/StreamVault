"""Recording settings and generated codec files share the saving app's catalogue."""

from pathlib import Path
from threading import get_ident

import pytest

from app.models import GlobalSettings, RecordingSettings
from app.routes.live import get_live_streaming_service
from app.utils.async_db_utils import run_in_thread_pool
from starlette.requests import HTTPConnection
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_recording_settings_read_save_and_config_use_only_the_owner(
    proxy_applications,
):
    applications, databases, clients, queries = proxy_applications
    for index, (app, database) in enumerate(zip(applications, databases, strict=True)):
        app.state.settings.BASE_DIR = str(
            Path(app.state.settings.RECORDING_DIRECTORY) / "runtime"
        )
        with database.sync_session_factory() as session:
            row = session.query(RecordingSettings).one()
            row.default_quality = "720p" if index == 0 else "480p"
            row.output_directory = app.state.settings.RECORDING_DIRECTORY
            session.commit()
    queries.clear()
    first = await clients[0].get("/api/recording/settings")
    second = await clients[1].get("/api/recording/settings")
    assert first.status_code == second.status_code == 200
    assert first.json()["default_quality"] == "720p"
    assert second.json()["default_quality"] == "480p"
    payload = {**first.json(), "supported_codecs": "h264"}
    saved = await clients[0].post("/api/recording/settings", json=payload)
    assert saved.status_code == 200
    assert saved.json()["supported_codecs"] == "h264"
    request_queries = list(queries)
    with databases[0].sync_session_factory() as session:
        assert session.query(GlobalSettings).one().supported_codecs == "h264"
    with databases[1].sync_session_factory() as session:
        assert (
            session.query(GlobalSettings).one().supported_codecs
            == second.json()["supported_codecs"]
        )
    own = (
        Path(applications[0].state.settings.BASE_DIR)
        / "config/streamlink/config.twitch"
    )
    peer = (
        Path(applications[1].state.settings.BASE_DIR)
        / "config/streamlink/config.twitch"
    )
    assert "twitch-supported-codecs=h264\n" in own.read_text()
    assert not peer.exists()
    assert request_queries and all(
        thread != get_ident() for thread, _ in request_queries
    )


@pytest.mark.asyncio
async def test_live_child_uses_the_same_owned_configuration_directory(
    proxy_applications,
):
    applications, _, _, _ = proxy_applications
    app = applications[0]
    app.state.settings.BASE_DIR = str(
        Path(app.state.settings.RECORDING_DIRECTORY) / "runtime"
    )
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    actor = await run_in_thread_pool(get_live_streaming_service, connection)
    try:
        command = await actor._build_streamlink_command("fixture-channel", "best")
        expected = Path(app.state.settings.BASE_DIR) / "config/streamlink/config.twitch"
        assert command[command.index("--config") + 1] == str(expected)
        manager = app.state.recording_manager
        assert manager.process_manager.streamlink_config_directory == expected.parent
    finally:
        await actor.stop()
        from app.lifespan import _close_application_twitch

        await _close_application_twitch(app)
        await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
