"""Recording credentials are selected by the owning DB/settings before HTTP I/O."""

import asyncio
import importlib
import json
from datetime import datetime, timedelta, timezone
from threading import get_ident
from time import monotonic

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import GlobalSettings, Stream
from app.lifespan import _close_application_twitch
from app.services.http_client import HTTPClientError, HTTPReply
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.exceptions import ProcessError
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.proxy_encryption import get_proxy_encryption
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


def scoped_process_manager(database, settings):
    async def post_processing(recording_id, path):
        return None

    return ProcessManager.for_application(
        config_manager=ConfigManager(
            session_factory=database.sync_session_factory, settings=settings
        ),
        post_processing_callback=post_processing,
        upstream_coordinator=TwitchUpstreamCoordinator(
            database.sync_session_factory, monotonic_clock=monotonic
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["environment", "database_manual"])
async def test_recording_token_uses_owned_closed_catalogue_and_reusable_validation_pool(
    proxy_applications, monkeypatch, source
):
    applications, databases, _, queries = proxy_applications
    module = importlib.import_module("app.services.system.twitch_token_service")
    writers, handlers, requests, peers = [], set(), [], []
    actors = []

    async def receive(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        writers.append(writer)
        peers.append(writer.get_extra_info("peername"))
        try:
            while True:
                header = (await reader.readuntil(b"\r\n\r\n")).decode("ascii")
                assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
                requests.append(header)
                payload = json.dumps(
                    {"client_id": "fixture-client", "expires_in": 7200}
                ).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                    + str(len(payload)).encode()
                    + b"\r\n\r\n"
                    + payload
                )
                await writer.drain()
        except asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            handlers.discard(task)

    server = await asyncio.start_server(receive, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    monkeypatch.setattr(
        module.TwitchTokenService, "VALIDATE_URL", f"http://127.0.0.1:{port}/validate"
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("No foreign settings or generated cipher is permitted")

    try:
        for index, (app, database) in enumerate(
            zip(applications, databases, strict=True)
        ):
            settings = dependencies.resolve_app_settings(app)
            settings.TWITCH_OAUTH_TOKEN = f"fixture-environment-{index}"
            with database.sync_session_factory() as session:
                stored = session.query(GlobalSettings).one()
                if source == "database_manual":
                    stored.twitch_access_token = get_proxy_encryption(session).encrypt(
                        f"fixture-database-{index}"
                    )
                    stored.twitch_refresh_token = None
                    stored.twitch_token_expires_at = datetime.now(timezone.utc).replace(
                        tzinfo=None
                    ) + timedelta(hours=2)
                    session.commit()
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            actors.append(
                await run_in_thread_pool(
                    dependencies.get_application_recording_manager, connection
                )
            )
        monkeypatch.setattr(module, "get_settings", forbidden)
        monkeypatch.setattr(module.ProxyEncryption, "_initialize_cipher", forbidden)
        queries.clear()
        for index, actor in enumerate(actors):
            expected = f"fixture-{'database' if source == 'database_manual' else 'environment'}-{index}"
            for _ in range(2):
                resolution = await actor.process_manager._resolve_recording_token()
                assert resolution is not None
                assert resolution.token == expected
                assert resolution.source == source
                assert resolution.live_valid is True
                assert resolution.definitive_invalid is False
                assert resolution.reason == "validated"
                assert (resolution.stored_version is not None) is (
                    source == "database_manual"
                )
                headers = {
                    name.lower(): value.strip()
                    for name, value in (
                        line.split(":", 1)
                        for line in requests[-1].split("\r\n")[1:]
                        if ":" in line
                    )
                }
                assert headers["authorization"] == f"OAuth {expected}"
        assert len(requests) == 4
        assert len(peers) == 2 and peers[0] != peers[1]
        relevant = [thread for thread, sql in queries if "global_settings" in sql]
        assert relevant and get_ident() not in relevant
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        server.close()
        for writer in writers:
            writer.close()
        if handlers:
            await asyncio.gather(*list(handlers), return_exceptions=True)
        await server.wait_closed()
        for actor in actors:
            await actor.process_manager.cleanup_all()
        for app in applications:
            await _close_application_twitch(app)
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()


@pytest.mark.asyncio
async def test_parallel_recording_token_operations_are_independently_owned(
    proxy_applications, monkeypatch
):
    applications, databases, _, _ = proxy_applications
    app = applications[0]
    dependencies.resolve_app_settings(app).TWITCH_OAUTH_TOKEN = "fixture-parallel"
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )
    barrier = asyncio.Barrier(2)
    requests = []

    async def request(*args, **kwargs):
        requests.append(kwargs)
        # Another operation may legitimately be reading in its own DB worker.
        await barrier.wait()
        return HTTPReply(200, {}, b'{"client_id":"fixture-client","expires_in":7200}')

    monkeypatch.setattr(service.http_client, "request", request)
    try:
        async with asyncio.timeout(5):
            results = await asyncio.gather(
                service.resolve_recording_token(), service.resolve_recording_token()
            )
        assert len(requests) == 2
        assert not service._supervisor.task_names
        assert all(
            result.token == "fixture-parallel" and result.live_valid
            for result in results
        )
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_standalone_recording_shutdown_closes_its_owned_credential_client(
    proxy_applications,
):
    applications, databases, _, _ = proxy_applications
    manager = scoped_process_manager(
        databases[0], dependencies.resolve_app_settings(applications[0])
    )
    service = manager._get_twitch_token_service()
    client = await service.http_client._get_client()
    try:
        assert not client.is_closed
        await manager.graceful_shutdown()
        assert client.is_closed
        assert service._supervisor.closed
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_stopped_recording_manager_rejects_before_new_credential_work(
    proxy_applications, monkeypatch, tmp_path
):
    applications, databases, _, _ = proxy_applications
    manager = scoped_process_manager(
        databases[0], dependencies.resolve_app_settings(applications[0])
    )
    await manager.graceful_shutdown()
    calls = []

    async def forbidden():
        calls.append("credential-resolution")
        raise AssertionError("A stopped owner must not begin new credential work")

    monkeypatch.setattr(manager, "_resolve_recording_token", forbidden)
    with pytest.raises(ProcessError, match="shutting down"):
        await manager.start_recording_process(
            Stream(id=1), str(tmp_path / "never.ts"), "best"
        )
    assert not calls
    assert not (tmp_path / "never.ts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ["clear", "manual", "invalidated"])
async def test_late_provider_reply_never_replaces_a_newer_credential_decision(
    proxy_applications, monkeypatch, replacement
):
    applications, databases, _, _ = proxy_applications
    app, database = applications[0], databases[0]
    dependencies.resolve_app_settings(app).TWITCH_OAUTH_TOKEN = None
    with database.sync_session_factory() as session:
        row = session.query(GlobalSettings).one()
        encryption = get_proxy_encryption(session)
        row.twitch_access_token = encryption.encrypt("fixture-old-access")
        row.twitch_refresh_token = (
            None
            if replacement == "invalidated"
            else encryption.encrypt("fixture-old-refresh")
        )
        row.twitch_token_expires_at = datetime.now(timezone.utc).replace(
            tzinfo=None
        ) - timedelta(hours=1)
        session.commit()
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )
    original = await service.get_state()
    assert original is not None
    calls = []

    async def provider(method, url, **kwargs):
        calls.append(method)
        if replacement == "invalidated":
            version = service._stored_token_version(original)
            assert version is not None
            assert await service.invalidate_recording_token(version)
        elif method == "POST":
            if replacement == "clear":
                assert await service.clear_tokens()
            else:
                assert (await service.store_manual_access_token("fixture-new-manual"))[
                    0
                ]
            return HTTPReply(
                200,
                {},
                b'{"access_token":"fixture-late-access","refresh_token":"fixture-late-refresh","expires_in":7200}',
            )
        return HTTPReply(200, {}, b'{"client_id":"fixture-client","expires_in":7200}')

    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        if replacement == "invalidated":
            assert await service.revalidate_stored_manual_token(original) is False
        else:
            resolution = await service.resolve_recording_token()
            assert resolution.token is None
            assert calls.count("POST") == 1
        current = await service.get_state()
        assert current is not None
        if replacement == "clear":
            assert current.twitch_access_token is None
            assert current.twitch_refresh_token is None
            assert current.twitch_token_expires_at is None
        elif replacement == "manual":
            assert current.twitch_refresh_token is None
            assert await service.get_valid_access_token() == "fixture-new-manual"
        else:
            assert (
                current.twitch_token_expires_at
                == service.RECORDING_INVALIDATED_TOKEN_EXPIRY
            )
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_twitch_status_http_uses_only_its_factory_environment(
    proxy_applications,
):
    applications, databases, clients, queries = proxy_applications
    dependencies.resolve_app_settings(
        applications[0]
    ).TWITCH_OAUTH_TOKEN = "fixture-status"
    dependencies.resolve_app_settings(applications[1]).TWITCH_OAUTH_TOKEN = None
    try:
        for index, client in enumerate(clients):
            queries.clear()
            response = await client.get("/api/twitch/connection-status")
            assert response.status_code == 200
            assert response.json() == {
                "connected": index == 0,
                "valid": index == 0,
                "expires_at": None,
                "source": "environment" if index == 0 else None,
                "has_env_token": index == 0,
            }
            relevant = [thread for thread, sql in queries if "global_settings" in sql]
            assert relevant and get_ident() not in relevant
            assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for app in applications:
            await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_twitch_manual_and_disconnect_http_publish_only_to_the_owner(
    proxy_applications, monkeypatch
):
    applications, databases, clients, queries = proxy_applications
    connection = HTTPConnection({"type": "http", "app": applications[0], "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )
    seen = []
    pool_observations = []

    async def provider(method, url, **kwargs):
        pool_observations.append([db.sync_engine.pool.checkedout() for db in databases])
        seen.append(kwargs["headers"]["Authorization"])
        return HTTPReply(200, {}, b'{"client_id":"fixture-client","expires_in":7200}')

    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        queries.clear()
        response = await clients[0].post(
            "/api/twitch/manual-token", json={"token": "OAuth fixture-manual"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Twitch OAuth token saved",
            "expires_in": 7200,
        }
        assert seen == ["OAuth fixture-manual"]
        assert pool_observations == [[0, 0]]
        relevant = [thread for thread, sql in queries if "global_settings" in sql]
        assert relevant and get_ident() not in relevant
        with databases[0].sync_session_factory() as session:
            row = session.query(GlobalSettings).one()
            assert row.twitch_access_token != "fixture-manual"
            assert (
                get_proxy_encryption(session).decrypt(row.twitch_access_token)
                == "fixture-manual"
            )
            assert row.twitch_refresh_token is None
        with databases[1].sync_session_factory() as session:
            assert session.query(GlobalSettings).one().twitch_access_token is None
        response = await clients[0].post("/api/twitch/disconnect")
        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Twitch account disconnected",
        }
        with databases[0].sync_session_factory() as session:
            row = session.query(GlobalSettings).one()
            assert (
                row.twitch_access_token,
                row.twitch_refresh_token,
                row.twitch_token_expires_at,
            ) == (None, None, None)
    finally:
        for app in applications:
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["quality-options", "codec-options"])
async def test_settings_auth_options_resolve_only_the_owning_token_service(
    proxy_applications, path
):
    applications, databases, clients, queries = proxy_applications
    dependencies.resolve_app_settings(
        applications[0]
    ).TWITCH_OAUTH_TOKEN = "fixture-options"
    dependencies.resolve_app_settings(applications[1]).TWITCH_OAUTH_TOKEN = None
    try:
        for index, client in enumerate(clients):
            queries.clear()
            response = await client.get(f"/api/settings/{path}")
            assert response.status_code == 200
            assert response.json()["oauth_configured"] is (index == 0)
            relevant = [thread for thread, sql in queries if "global_settings" in sql]
            assert relevant and get_ident() not in relevant
            assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for app in applications:
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["clear", "replace", "invalidate", "environment"])
async def test_late_recording_validation_cannot_return_retired_credentials(
    proxy_applications, monkeypatch, change
):
    applications, databases, _, _ = proxy_applications
    app, database = applications[0], databases[0]
    settings = dependencies.resolve_app_settings(app)
    settings.TWITCH_OAUTH_TOKEN = "fixture-retired" if change == "environment" else None
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )

    def seed():
        with database.sync_session_factory() as session:
            row = session.query(GlobalSettings).one()
            row.twitch_access_token = get_proxy_encryption(session).encrypt(
                "fixture-retired"
            )
            row.twitch_token_expires_at = datetime.now(timezone.utc).replace(
                tzinfo=None
            ) + timedelta(hours=2)
            session.commit()

    if change != "environment":
        await run_in_thread_pool(seed)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def provider(method, url, **kwargs):
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        assert kwargs["headers"]["Authorization"] == "OAuth fixture-retired"
        arrived.set()
        await release.wait()
        return HTTPReply(200, {}, b'{"client_id":"fixture-client","expires_in":7200}')

    monkeypatch.setattr(service.http_client, "request", provider)
    task = asyncio.create_task(service.resolve_recording_token())
    try:
        await asyncio.wait_for(arrived.wait(), 2)
        if change in {"clear", "environment"}:
            assert await service.clear_tokens()
        elif change == "replace":
            assert await service.store_oauth_tokens(
                "fixture-replacement", "fixture-refresh", 7200
            )
        else:
            state = await service.get_state()
            assert state is not None
            version = service._stored_token_version(state)
            assert version is not None
            assert await service.invalidate_recording_token(version)
        release.set()
        result = await task
        assert result.token is None
        assert result.live_valid is False
        assert result.definitive_invalid is False
        assert result.reason == "credential_changed"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_refresh_validation_failure_never_invalidates_a_later_publication(
    proxy_applications, monkeypatch
):
    applications, databases, _, _ = proxy_applications
    app = applications[0]
    dependencies.resolve_app_settings(app).TWITCH_OAUTH_TOKEN = None
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )
    assert await service.store_oauth_tokens("fixture-old", "fixture-refresh", -1)
    published = []
    native_in_db = service._in_db

    async def replace_after_commit(operation):
        value = await native_in_db(operation)
        if operation.__name__ == "publish" and value:
            assert await service.store_oauth_tokens(
                "fixture-new-decision", "fixture-new-refresh", 7200
            )
            published.append(await service.get_state())
        return value

    async def provider(method, url, **kwargs):
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        if method == "POST":
            return HTTPReply(
                200, {}, b'{"access_token":"fixture-refreshed","expires_in":7200}'
            )
        raise HTTPClientError("status", status_code=401)

    monkeypatch.setattr(service, "_in_db", replace_after_commit)
    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        result = await service.resolve_recording_token()
        assert result.token is None
        assert len(published) == 1
        assert await service.get_state() == published[0]
    finally:
        await _close_application_twitch(app)
