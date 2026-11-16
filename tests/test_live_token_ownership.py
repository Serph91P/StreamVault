"""Live child auth/proxy inputs use closed scopes belonging to their application."""

from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.lifespan import _close_application_twitch
from app.services.live_streaming_service import LiveStreamingService
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
async def test_live_command_uses_only_its_owned_credential_and_proxy_catalogue(
    proxy_applications,
):
    applications, databases, _, queries = proxy_applications
    actors = []
    try:
        for index, app in enumerate(applications):
            settings = dependencies.resolve_app_settings(app)
            settings.TWITCH_OAUTH_TOKEN = f"fixture-live-{index}"
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            token_service = await run_in_thread_pool(
                dependencies.get_application_twitch_token_service, connection
            )
            proxy_service = await run_in_thread_pool(
                dependencies.get_proxy_health_service, connection
            )
            actors.append(
                LiveStreamingService(
                    session_factory=databases[index].sync_session_factory,
                    settings=settings,
                    token_service=token_service,
                    proxy_service=proxy_service,
                )
            )
        for index, actor in enumerate(actors):
            queries.clear()
            command = await actor._build_streamlink_command(
                "fixture-channel", "best", enhanced_quality=True
            )
            assert (
                f"--twitch-api-header=Authorization=OAuth fixture-live-{index}"
                in command
            )
            assert any(f"owner-{index}.invalid:8080" in arg for arg in command)
            assert not any(f"owner-{1 - index}.invalid:8080" in arg for arg in command)
            assert queries and all(thread != get_ident() for thread, _ in queries)
            assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        await actors[0].stop()
        assert (
            await applications[0].state.twitch_token_service.get_valid_access_token()
            == "fixture-live-0"
        )
        assert "--twitch-api-header=Authorization=OAuth fixture-live-1" in await actors[
            1
        ]._build_streamlink_command("fixture-channel", "best", enhanced_quality=True)
    finally:
        for actor in actors:
            await actor.stop()
        for app in applications:
            await _close_application_twitch(app)
