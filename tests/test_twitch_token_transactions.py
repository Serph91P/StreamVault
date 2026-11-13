"""Actual token-catalogue transactions fail closed without losing prior decisions."""

from datetime import datetime, timedelta, timezone
import asyncio

import pytest
from sqlalchemy import event
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import _close_application_twitch
from app.services.http_client import HTTPReply
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["oauth", "manual", "clear", "invalidate", "revalidate", "refresh"]
)
async def test_failed_token_commit_retains_the_last_durable_decision(
    proxy_applications, monkeypatch, operation
):
    applications, databases, _, _ = proxy_applications
    app, database = applications[0], databases[0]
    settings = dependencies.resolve_app_settings(app)
    settings.TWITCH_OAUTH_TOKEN = None
    connection = HTTPConnection({"type": "http", "app": app, "headers": []})
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service, connection
    )
    assert await service.store_oauth_tokens(
        "fixture-prior", "fixture-refresh", -1 if operation == "refresh" else 7200
    )
    if operation == "revalidate":

        def make_manual():
            from app.models import GlobalSettings

            with database.sync_session_factory() as session:
                row = session.query(GlobalSettings).one()
                row.twitch_refresh_token = None
                row.twitch_token_expires_at = datetime.now(timezone.utc).replace(
                    tzinfo=None
                ) - timedelta(minutes=1)
                session.commit()

        await run_in_thread_pool(make_manual)
    before = await service.get_state()
    assert before is not None

    def reject_commit(session):
        raise RuntimeError("fixture commit failure")

    def failing_session():
        session = database.sync_session_factory()
        event.listen(session, "before_commit", reject_commit)
        return session

    async def provider(method, url, **kwargs):
        assert database.sync_engine.pool.checkedout() == 0
        payload = (
            b'{"access_token":"fixture-new","refresh_token":"fixture-new-refresh","expires_in":7200}'
            if method == "POST"
            else b'{"client_id":"fixture-client","expires_in":7200}'
        )
        return HTTPReply(200, {}, payload)

    monkeypatch.setattr(service, "_session_factory", failing_session)
    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        if operation == "oauth":
            assert (
                await service.store_oauth_tokens(
                    "fixture-new", "fixture-new-refresh", 7200
                )
                is False
            )
        elif operation == "manual":
            success, validation = await service.store_manual_access_token("fixture-new")
            assert success is False
            assert validation is not None and validation["expires_in"] == 7200
        elif operation == "clear":
            settings.TWITCH_OAUTH_TOKEN = "fixture-fallback"
            assert await service.clear_tokens() is False
            assert settings.TWITCH_OAUTH_TOKEN == "fixture-fallback"
        elif operation == "invalidate":
            version = service._stored_token_version(before)
            assert version is not None
            assert await service.invalidate_recording_token(version) is False
        elif operation == "revalidate":
            assert await service.revalidate_stored_manual_token(before) is False
        else:
            assert await service.get_valid_access_token() is None
        assert await service.get_state() == before
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("refresh", [False, True])
async def test_owned_oauth_selection_reuses_fresh_tokens_and_singleflights_refresh(
    proxy_applications, monkeypatch, refresh
):
    applications, databases, _, _ = proxy_applications
    app = applications[0]
    dependencies.resolve_app_settings(app).TWITCH_OAUTH_TOKEN = None
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    assert await service.store_oauth_tokens(
        "fixture-current", "fixture-refresh", -1 if refresh else 7200
    )
    requests = []
    waiting = asyncio.Event()

    class ObservedLock(asyncio.Lock):
        async def __aenter__(self):
            if self.locked():
                waiting.set()
            return await super().__aenter__()

    service._refresh_lock = ObservedLock()

    async def provider(method, url, **kwargs):
        requests.append(method)
        assert await asyncio.wait_for(waiting.wait(), 2)
        # The peer's snapshot can still be reading until it joins the lock.
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        return HTTPReply(
            200, {}, b'{"access_token":"fixture-renewed","expires_in":7200}'
        )

    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        tokens = await asyncio.gather(
            service.get_valid_access_token(), service.get_valid_access_token()
        )
        assert tokens == ["fixture-renewed" if refresh else "fixture-current"] * 2
        assert requests == (["POST"] if refresh else [])
        assert not service._supervisor.task_names
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_owned_token_close_cancels_pending_validation_and_rejects_new_work(
    proxy_applications, monkeypatch
):
    applications, _, _, _ = proxy_applications
    app = applications[0]
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    entered, stopped = asyncio.Event(), asyncio.Event()

    async def provider(*args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    monkeypatch.setattr(service.http_client, "request", provider)
    request = asyncio.create_task(service.validate_token("fixture-pending"))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await service.close()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert stopped.is_set()
        assert not service._supervisor.task_names
        with pytest.raises(RuntimeError, match="closed"):
            await service.validate_token("fixture-late")
        await service.close()
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("callback_failure", [False, True])
async def test_token_change_callback_observes_committed_state_without_a_refresh_lock(
    proxy_applications, callback_failure
):
    applications, databases, _, _ = proxy_applications
    app = applications[0]
    dependencies.resolve_app_settings(app).TWITCH_OAUTH_TOKEN = None
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    observed = []

    async def callback():
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        observed.append(await service.get_valid_access_token())
        if callback_failure:
            raise RuntimeError("fixture configuration failure")

    service._on_tokens_changed = callback
    try:
        async with asyncio.timeout(3):
            assert await service.store_oauth_tokens(
                "fixture-committed", "fixture-refresh", 7200
            )
        assert observed == ["fixture-committed"]
        assert not service._supervisor.task_names
    finally:
        await _close_application_twitch(app)


@pytest.mark.asyncio
async def test_cancelled_token_close_still_awaits_its_resource_close(
    proxy_applications, monkeypatch
):
    applications, _, _, _ = proxy_applications
    app = applications[0]
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )
    entered, release = asyncio.Event(), asyncio.Event()
    native_close = service.http_client.close

    async def close():
        entered.set()
        await release.wait()
        await native_close()

    monkeypatch.setattr(service.http_client, "close", close)
    task = asyncio.create_task(service.close())
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        for _ in range(10):
            await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"[]", b"invalid-json", b"null"])
async def test_public_token_validation_rejects_malformed_provider_documents(
    proxy_applications, monkeypatch, body
):
    applications, _, _, _ = proxy_applications
    app = applications[0]
    service = await run_in_thread_pool(
        dependencies.get_application_twitch_token_service,
        HTTPConnection({"type": "http", "app": app, "headers": []}),
    )

    async def provider(*args, **kwargs):
        return HTTPReply(200, {}, body)

    monkeypatch.setattr(service.http_client, "request", provider)
    try:
        assert await service.validate_token("fixture-validation") is None
    finally:
        await _close_application_twitch(app)
