"""Follow enumeration against a local HTTP provider, never a Twitch account."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from fastapi import FastAPI

import app.services.api.twitch_api as api_module
from app.services.api.twitch_api import TwitchAPIService


def follow(number):
    return {
        "broadcaster_id": str(number),
        "broadcaster_login": f"channel{number}",
        "broadcaster_name": f"Channel {number}",
        "followed_at": "2026-01-01T00:00:00Z",
    }


@asynccontextmanager
async def provider(pages, *, delay=0.0):
    requests = []

    async def respond(request):
        requests.append((dict(request.query), request.headers.get("Authorization")))
        await asyncio.sleep(delay)
        page = pages[min(len(requests) - 1, len(pages) - 1)]
        if isinstance(page, int):
            return web.Response(status=page, text="synthetic-private-provider-body")
        if isinstance(page, str):
            return web.Response(text=page)
        return web.json_response(page)

    app = web.Application()
    app.router.add_get("/channels/followed", respond)
    async with TestServer(app) as server:
        api = TwitchAPIService()
        api.base_url = str(server.make_url("/")).rstrip("/")
        yield api, requests


@pytest.mark.parametrize("count", [0, 1, 20, 21, 62])
async def test_all_pages_reach_caller_with_user_token(count):
    rows = [follow(i) for i in range(count)]
    pages = [
        {
            "data": rows[start : start + 20],
            "total": count,
            "pagination": {"cursor": str(start + 20)} if start + 20 < count else {},
        }
        for start in range(0, count, 20)
    ] or [{"data": [], "total": 0, "pagination": {}}]
    async with provider(pages) as (api, requests):
        result = await api.get_user_followed_streamers(
            "synthetic-user", "synthetic-user-token"
        )
    assert result == rows
    assert [query.get("after") for query, _ in requests] == [None] + [
        str(start) for start in range(20, count, 20)
    ]
    assert all(query["user_id"] == "synthetic-user" for query, _ in requests)
    assert all(token == "Bearer synthetic-user-token" for _, token in requests)


async def test_empty_intermediate_page_and_changing_total_do_not_truncate_or_duplicate():
    pages = [
        {"data": [follow(1)], "total": 1, "pagination": {"cursor": "a"}},
        {"data": [], "total": 0, "pagination": {"cursor": "b"}},
        {"data": [follow(1), follow(2)], "total": 2, "pagination": {}},
    ]
    async with provider(pages) as (api, requests):
        result = await api.get_user_followed_streamers("user", "token")
    assert result == [follow(1), follow(2)]
    assert [query.get("after") for query, _ in requests] == [None, "a", "b"]


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_late_failure_is_not_empty_or_partial_success(status, caplog):
    async with provider(
        [{"data": [follow(1)], "pagination": {"cursor": "next"}}, status]
    ) as (api, requests):
        with pytest.raises(ConnectionError):
            await api.get_user_followed_streamers("user", "synthetic-user-token")
    assert len(requests) == 2
    assert "synthetic-private-provider-body" not in caplog.text
    assert "synthetic-user-token" not in caplog.text


@pytest.mark.parametrize(
    "bad_page",
    [
        [],
        {},
        {"data": {}},
        {"data": [None]},
        {"data": [{"broadcaster_login": "missing-id"}]},
        {"data": [follow(1)], "pagination": []},
        {"data": [follow(1)], "pagination": {"cursor": 123}},
    ],
)
async def test_malformed_page_is_explicit_error(bad_page):
    async with provider([bad_page]) as (api, _):
        with pytest.raises(ValueError):
            await api.get_user_followed_streamers("user", "token")


async def test_repeated_cursor_stops_without_success():
    async with provider(
        [
            {"data": [follow(1)], "pagination": {"cursor": "repeat"}},
        ]
    ) as (api, requests):
        with pytest.raises(ValueError):
            await api.get_user_followed_streamers("user", "token")
    assert len(requests) == 2


async def test_page_budget_bounds_unique_cursors(monkeypatch):
    monkeypatch.setattr(api_module, "FOLLOW_MAX_PAGES", 3, raising=False)
    pages = [{"data": [follow(i)], "pagination": {"cursor": str(i)}} for i in range(10)]
    async with provider(pages) as (api, requests):
        with pytest.raises(ValueError):
            await api.get_user_followed_streamers("user", "token")
    assert len(requests) == 3


async def test_timeout_is_not_success(monkeypatch):
    monkeypatch.setattr(api_module, "FOLLOW_FETCH_TIMEOUT", 0.02, raising=False)
    async with provider([{"data": [], "pagination": {}}], delay=0.1) as (api, _):
        with pytest.raises(TimeoutError):
            await api.get_user_followed_streamers("user", "token")


async def test_cancellation_is_not_swallowed():
    async with provider([{"data": [], "pagination": {}}], delay=0.1) as (api, requests):
        task = asyncio.create_task(api.get_user_followed_streamers("user", "token"))
        async with asyncio.timeout(2):
            while not requests:
                await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(requests) == 1


@pytest.mark.parametrize("late_failure", [False, True, "invalid-json"])
async def test_registered_route_exposes_complete_selection_or_error(
    monkeypatch, late_failure
):
    from app.routes.twitch_auth import get_twitch_oauth_service, router
    from app.services.api import twitch_oauth_service as oauth_module
    from app.services.api.twitch_oauth_service import TwitchOAuthService
    from app.services.streamer_service import StreamerService

    async def authenticated_user(_token):
        return "synthetic-user"

    pages = [
        {"data": [follow(1)], "pagination": {"cursor": "next"}},
        ("invalid-json" if late_failure == "invalid-json" else 429)
        if late_failure
        else {"data": [follow(2)], "pagination": {}},
    ]
    async with provider(pages) as (api, requests):
        monkeypatch.setattr(oauth_module, "twitch_api", api)
        service = TwitchOAuthService(Mock(spec=StreamerService))
        # Authentication is the separate #1027 contract; enumeration stays real.
        monkeypatch.setattr(service, "_get_authenticated_user_id", authenticated_user)
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_twitch_oauth_service] = lambda: service
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/twitch/followed-channels",
                params={"access_token": "synthetic-user-token"},
            )
    assert len(requests) == 2
    if late_failure:
        assert response.status_code == 502
        assert "channels" not in response.json()
    else:
        assert response.status_code == 200
        assert [channel["login"] for channel in response.json()["channels"]] == [
            "channel1",
            "channel2",
        ]


async def test_later_page_selection_imports_once_without_resetting_settings(
    monkeypatch, tmp_path
):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.database import Base
    from app.models import GlobalSettings, Streamer, StreamerRecordingSettings
    from app.routes.twitch_auth import get_twitch_oauth_service, router
    from app.services.api import twitch_oauth_service as oauth_module
    from app.services.api.twitch_oauth_service import TwitchOAuthService
    from app.services.streamer_service import StreamerService
    from app.events.handler_registry import EventHandlerRegistry
    from app.services.communication.websocket_manager import ConnectionManager

    engine = create_engine(f"sqlite:///{tmp_path / 'import.db'}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            streamers = StreamerService(
                db, ConnectionManager(), Mock(spec=EventHandlerRegistry)
            )

            async def user_data(login):
                return {
                    "id": login.removeprefix("channel"),
                    "login": login,
                    "profile_image_url": "",
                }

            # Only external identity/image/EventSub boundaries are controlled.
            monkeypatch.setattr(streamers.twitch_service, "get_user_data", user_data)
            monkeypatch.setattr(
                streamers.twitch_service,
                "get_stream_info",
                AsyncMock(return_value=None),
            )
            monkeypatch.setattr(
                streamers.twitch_service, "subscribe_to_events", AsyncMock()
            )
            monkeypatch.setattr(
                streamers.image_service,
                "download_profile_image",
                AsyncMock(return_value=""),
            )
            existing = streamers.repository.create_streamer(await user_data("channel1"))
            channel_settings = (
                db.query(StreamerRecordingSettings)
                .filter_by(streamer_id=existing.id)
                .one()
            )
            channel_settings.enabled = False
            db.add(GlobalSettings(notifications_enabled=False, supported_codecs="h264"))
            db.commit()
            before_global = db.execute(select(GlobalSettings.__table__)).all()
            before_channel = db.execute(
                select(StreamerRecordingSettings.__table__).where(
                    StreamerRecordingSettings.streamer_id == existing.id
                )
            ).all()

            service = TwitchOAuthService(streamers)
            monkeypatch.setattr(
                service,
                "_get_authenticated_user_id",
                AsyncMock(return_value="synthetic-user"),
            )
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_twitch_oauth_service] = lambda: service
            pages = [
                {"data": [follow(1)], "pagination": {"cursor": "next"}},
                {"data": [follow(1), follow(2)], "pagination": {}},
            ]
            async with provider(pages) as (api, _):
                monkeypatch.setattr(oauth_module, "twitch_api", api)
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        "/api/twitch/followed-channels",
                        params={"access_token": "synthetic-user-token"},
                    )
                    assert response.status_code == 200
                    selection = response.json()["channels"]
                    assert [row["id"] for row in selection] == ["1", "2"]
                    for _ in range(2):
                        imported = await client.post(
                            "/api/twitch/import-streamers", json=selection
                        )
                        assert imported.status_code == 200
                        assert imported.json()["failed"] == []
            db.expire_all()
            assert db.execute(select(GlobalSettings.__table__)).all() == before_global
            assert (
                db.execute(
                    select(StreamerRecordingSettings.__table__).where(
                        StreamerRecordingSettings.streamer_id == existing.id
                    )
                ).all()
                == before_channel
            )
        with Session(engine) as fresh:
            assert fresh.scalars(
                select(Streamer.twitch_id).order_by(Streamer.twitch_id)
            ).all() == ["1", "2"]
            assert fresh.query(StreamerRecordingSettings).count() == 2
    finally:
        engine.dispose()
