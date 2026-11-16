"""Provider failure outcomes stay stable without echoing provider diagnostics."""

from unittest.mock import Mock

import pytest

from app.events.handler_registry import EventHandlerRegistry
from app.services.api.twitch_api import TwitchAPIService
from app.services.streamers.twitch_integration_service import TwitchIntegrationService
from app.services.streamer_service import StreamerService
from app.services.communication.websocket_manager import ConnectionManager
from app.services.unified_image_service import UnifiedImageService
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


@pytest.fixture
def streamer_actor(image_applications):
    _, databases, _, _ = image_applications
    api = Mock(spec=TwitchAPIService)
    images = Mock(spec=UnifiedImageService)
    registry = Mock(spec=EventHandlerRegistry)
    manager = Mock(spec=ConnectionManager)
    user = {
        "id": "42",
        "login": "added",
        "display_name": "Added",
        "profile_image_url": "https://images.invalid/added.jpg",
    }
    api.get_users_by_login.return_value = [user]
    api.get_users_by_id.return_value = [user]
    api.get_streams.return_value = []
    api.get_games_by_id.return_value = [
        {"id": "game", "box_art_url": "https://images.invalid/{width}x{height}.jpg"}
    ]
    images.download_profile_image.return_value = "/data/images/profiles/added.jpg"
    images.download_banner_image.return_value = "/data/images/banners/added.jpg"
    images.update_streamer_profile_image.return_value = False
    images.get_cached_profile_image.return_value = None
    actor = StreamerService(
        session_factory=databases[0].sync_session_factory,
        websocket_manager=manager,
        event_registry=registry,
        twitch_api=api,
        image_service=images,
    )
    return actor, api, images, registry, manager, databases[0]


@pytest.mark.asyncio
async def test_streamer_provider_delegates_and_image_fallback_keep_existing_values(
    streamer_actor,
):
    actor, api, images, _, _, database = streamer_actor
    assert actor.twitch_api is api
    assert (await actor.get_users_by_login(["added"]))[0]["id"] == "42"
    assert (await actor.get_streamer_info("42"))["login"] == "added"
    assert (await actor.get_user_data("added"))["display_name"] == "Added"
    assert await actor.get_stream_info("42") is None
    assert await actor.check_streamer_live_status("42") is False
    api.get_streams.return_value = [{"user_id": "42", "title": "Live"}]
    assert await actor.check_streamer_live_status("42") is True
    assert (await actor.get_stream_info("42"))["title"] == "Live"
    assert (await actor.get_game_data("game"))[
        "box_art_url"
    ] == "https://images.invalid/285x380.jpg"
    await actor.subscribe_to_events("42")
    assert (
        await actor.download_profile_image("https://images.invalid/a.jpg", "42")
        == "/data/images/profiles/added.jpg"
    )
    images.download_profile_image.return_value = None
    assert (
        await actor.download_profile_image("https://images.invalid/a.jpg", "42")
        == "https://images.invalid/a.jpg"
    )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_missing_or_invalid_provider_identity_never_adds_a_database_row(
    streamer_actor,
):
    actor, api, _, _, _, database = streamer_actor
    api.get_users_by_login.return_value = []
    api.get_users_by_id.return_value = []
    assert await actor.add_streamer("missing") is None
    assert await actor.refresh_streamer_data(1) is False
    api.get_users_by_login.return_value = [{"id": None}]
    with pytest.raises(ValueError, match="Invalid Twitch user data"):
        await actor.add_streamer("invalid")
    assert [row.username for row in await actor.get_all_streamers()] == ["owner-0"]
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_optional_provider_failures_keep_committed_streamer_and_private_logs(
    streamer_actor, caplog
):
    actor, api, images, registry, _, database = streamer_actor
    private = "synthetic-private-provider-detail"
    api.get_users_by_login.return_value[0]["offline_image_url"] = (
        "https://images.invalid/banner.jpg"
    )
    images.download_banner_image.side_effect = RuntimeError(private)
    api.get_streams.side_effect = RuntimeError(private)
    registry.subscribe_to_events.side_effect = RuntimeError(private)
    registry.unsubscribe_from_events.side_effect = RuntimeError(private)
    created = await actor.add_streamer("added")
    assert (
        created is not None and created.username == "Added" and created.is_live is False
    )
    assert await actor.bulk_check_live_status() == {1: False, created.id: False}
    assert await actor.bulk_check_live_status([999]) == {}
    assert await actor.delete_streamer(created.id) == {
        "twitch_id": "42",
        "username": "Added",
    }
    assert [row.username for row in await actor.get_all_streamers()] == ["owner-0"]
    assert private not in caplog.text
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_notification_failure_after_commit_is_not_duplicate_creation_on_retry(
    streamer_actor, caplog
):
    actor, _, _, _, manager, database = streamer_actor
    private = "synthetic-private-notification-detail"
    manager.send_notification.side_effect = RuntimeError(private)
    with pytest.raises(RuntimeError):
        await actor.add_streamer("added")
    retried = await actor.add_streamer("added")
    assert retried is not None and retried.username == "Added"
    assert [row.username for row in await actor.get_all_streamers()] == [
        "Added",
        "owner-0",
    ]
    assert private not in caplog.text
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_streamer_integration_projects_existing_category_and_identity_values(
    streamer_actor,
):
    actor, api, _, _, _, _ = streamer_actor
    integration = actor.twitch_service
    api.get_games_by_name.return_value = [{"id": "game", "name": "Category"}]
    api.get_top_games.return_value = [
        {"id": "top", "box_art_url": "https://images.invalid/{width}/{height}.jpg"}
    ]
    api.search_categories.return_value = [
        {"id": "search", "box_art_url": "https://images.invalid/{width}/{height}.jpg"}
    ]
    assert await integration.get_categories(category_names=["Category"]) == [
        {"id": "game", "name": "Category"}
    ]
    assert (await integration.get_categories(category_ids=["game"]))[0]["id"] == "game"
    assert await integration.get_categories() == []
    assert (await integration.get_top_games())[0][
        "box_art_url"
    ] == "https://images.invalid/285/380.jpg"
    assert (await integration.search_categories("Category"))[0][
        "box_art_url"
    ] == "https://images.invalid/285/380.jpg"
    assert (await integration.get_multiple_user_info(["42"]))[0]["id"] == "42"
    assert await integration.validate_streamer_exists("added") is True
    assert await integration.get_streamer_followers("42") is None
    assert integration.get_twitch_profile_url("added") == "https://twitch.tv/added"
    assert integration.get_twitch_video_url("video") == "https://twitch.tv/videos/video"
    api.get_users_by_id.return_value = []
    api.get_users_by_login.return_value = []
    api.get_games_by_id.return_value = []
    assert await actor.get_streamer_info("42") is None
    assert await actor.get_game_data("missing") is None
    assert await integration.get_multiple_user_info(["42"]) == []
    assert await integration.validate_streamer_exists("missing") is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,args,expected,propagates",
    [
        ("get_user_data", ["owner"], None, False),
        ("get_stream_info", ["42"], None, False),
        ("get_game_data", ["42"], None, False),
        ("get_multiple_stream_info", [["42"]], [], False),
        ("get_multiple_user_info", [["42"]], [], False),
        ("subscribe_to_events", ["42"], None, True),
        ("unsubscribe_from_events", ["42"], None, True),
        ("get_categories", [["category"]], [], False),
        ("get_top_games", [], [], False),
        ("search_categories", ["category"], [], False),
        ("validate_streamer_exists", ["owner"], False, False),
        ("check_stream_status_bulk", [["42"]], {"42": False}, False),
        ("refresh_user_data", ["42"], None, False),
    ],
)
async def test_provider_failure_never_logs_private_exception_values(
    method, args, expected, propagates, caplog
):
    private = "synthetic-private-provider-response-do-not-echo"
    api = Mock(spec=TwitchAPIService)
    registry = Mock(spec=EventHandlerRegistry)
    for name in [
        "get_users_by_login",
        "get_users_by_id",
        "get_streams",
        "get_games_by_id",
        "get_games_by_name",
        "get_top_games",
        "search_categories",
    ]:
        getattr(api, name).side_effect = RuntimeError(private)
    registry.subscribe_to_events.side_effect = RuntimeError(private)
    registry.unsubscribe_from_events.side_effect = RuntimeError(private)
    actor = TwitchIntegrationService(registry, twitch_api=api)
    if propagates:
        with pytest.raises(RuntimeError):
            await getattr(actor, method)(*args)
    else:
        assert await getattr(actor, method)(*args) == expected
    assert caplog.records
    assert private not in caplog.text
