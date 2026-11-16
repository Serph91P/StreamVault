"""Recording requests preserve owner files, scalar settings and read fallback."""

import importlib
from datetime import datetime, timezone
from threading import get_ident

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError, TimeoutError

from app import dependencies
from app.lifespan import _close_application_logging
from app.models import Recording, RecordingSettings, Stream, StreamerRecordingSettings
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
async def test_streamer_settings_request_writes_only_its_owned_logging_files(
    image_applications, monkeypatch
):
    apps, databases, clients, queries = image_applications
    route = importlib.import_module("app.routes.recording")
    for app in apps:
        assert app.state.logging_service is None
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    own = await run_in_thread_pool(
        dependencies._get_application_logging_service, apps[0]
    )
    peer = await run_in_thread_pool(
        dependencies._get_application_logging_service, apps[1]
    )
    peer_images = await run_in_thread_pool(
        dependencies._get_application_image_service, apps[1]
    )
    monkeypatch.setattr(route, "logging_service", peer)
    monkeypatch.setattr(route, "unified_image_service", peer_images)

    def logs(service):
        return {
            str(path): path.read_bytes()
            for path in service.logs_base_dir.rglob("*.log")
        }

    peer_before = logs(peer)
    queries.clear()
    try:
        response = await clients[0].post(
            "/api/recording/streamers/1",
            json={
                "streamer_id": 1,
                "custom_filename": "fixture-template",
                "max_streams": 3,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["custom_filename"] == "fixture-template"
        assert queries and get_ident() not in {thread for thread, _ in queries}
        assert logs(peer) == peer_before, (
            "App A request wrote the default/peer B logger"
        )
        assert any(b"custom_filename" in data for data in logs(own).values())
        with databases[0].sync_session_factory() as session:
            row = (
                session.query(StreamerRecordingSettings).filter_by(streamer_id=1).one()
            )
            assert row.custom_filename == "fixture-template" and row.max_streams == 3
        with databases[1].sync_session_factory() as session:
            assert session.query(StreamerRecordingSettings).count() == 0
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        await _close_application_logging(apps[0])
        await _close_application_logging(apps[1])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["fallback", "empty", "other-sql", "unexpected", "recover"]
)
async def test_active_recordings_native_sql_failures_preserve_retry_and_cache_contract(
    image_applications, failure
):
    apps, databases, clients, queries = image_applications
    database = databases[0]

    def seed():
        with database.sync_session_factory() as session:
            session.add(Stream(id=70, streamer_id=1, title="owned active fixture"))
            session.flush()
            session.add(
                Recording(
                    id=7,
                    stream_id=70,
                    status="recording",
                    start_time=datetime.now(timezone.utc),
                )
            )
            session.commit()

    await run_in_thread_pool(seed)
    original = await clients[0].get("/api/recording/active")
    assert original.status_code == 200 and original.json()[0]["id"] == 7
    cache = apps[0].state.recording_status_cache
    cache.delete("active_recordings")
    if failure != "fallback":
        cache.delete("active_recordings_fallback")
    attempts = []

    def reject(_conn, _cursor, sql, *_):
        if "FROM recordings" not in sql:
            return
        attempts.append(get_ident())
        if failure == "recover" and len(attempts) > 2:
            return
        if failure == "other-sql":
            raise OperationalError(
                "synthetic SELECT", {}, RuntimeError("synthetic database fault")
            )
        if failure == "unexpected":
            raise RuntimeError("synthetic active query fault")
        raise TimeoutError("synthetic QueuePool timeout")

    event.listen(database.sync_engine, "before_cursor_execute", reject)
    try:
        response = await clients[0].get("/api/recording/active")
        assert response.status_code == 200
        if failure == "fallback":
            assert response.json() == original.json()
        elif failure == "recover":
            assert response.json()[0]["id"] == 7
        else:
            assert response.json() == []
        assert len(attempts) == (1 if failure in {"other-sql", "unexpected"} else 3)
        assert get_ident() not in attempts
        assert database.sync_engine.pool.checkedout() == 0
        assert (await clients[1].get("/api/recording/active")).json() == []
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", reject)


@pytest.mark.asyncio
async def test_malformed_stored_cleanup_policy_is_read_nonfatally_without_rewrite(
    image_applications,
):
    _, databases, clients, _ = image_applications
    database = databases[0]

    def seed():
        with database.sync_session_factory() as session:
            session.add(RecordingSettings(cleanup_policy="not-json"))
            session.commit()

    await run_in_thread_pool(seed)
    response = await clients[0].get("/api/recording/settings")
    assert response.status_code == 200 and response.json()["cleanup_policy"] is None
    with database.sync_session_factory() as session:
        assert session.query(RecordingSettings).one().cleanup_policy == "not-json"
    with databases[1].sync_session_factory() as session:
        assert session.query(RecordingSettings).count() == 0
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_filename_presets_http_contract_contains_renderable_media_templates(
    image_applications,
):
    _, _, clients, _ = image_applications
    response = await clients[0].get("/api/recording/filename-presets")
    assert response.status_code == 200 and response.json()["status"] == "success"
    entries = response.json()["data"]
    by_name = {entry["value"]: entry for entry in entries}
    assert len(by_name) == len(entries)
    assert by_name["default"]["label"] == "Default"
    assert {"plex", "emby", "jellyfin"} <= by_name.keys()
    default = by_name["default"]["description"].format(
        streamer="Fixture",
        year="2026",
        month="01",
        day="02",
        hour="03",
        minute="04",
        title="Title",
        game="Game",
    )
    assert default == "Fixture_2026-01-02_03-04_Title_Game"
    assert (
        by_name["plex"]["description"].format(
            streamer="Fixture", year="2026", month="01", episode=2, title="Title"
        )
        == "Season 2026-01/Fixture - S202601E02 - Title"
    )
