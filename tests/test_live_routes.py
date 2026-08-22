from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routes import live as live_routes
from app.services.live_streaming_service import TwitchUpstreamStopForbidden
from app.services.twitch_upstream_coordinator import TwitchUpstreamConflict


class JsonRequest:
    headers = {"content-type": "application/json"}

    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


class StreamerQuery:
    def __init__(self, streamers):
        self.streamers = streamers

    def all(self):
        return self.streamers

    def filter(self, *args):
        return self

    def first(self):
        return self.streamers[0] if self.streamers else None


class Database:
    def __init__(self, streamers):
        self.streamers = streamers

    def query(self, model):
        return StreamerQuery(self.streamers)


@pytest.mark.asyncio
async def test_start_route_normalizes_name_and_returns_idempotency(monkeypatch):
    streamer = SimpleNamespace(username="HandOfBlood", twitch_id="stable-42")
    calls = []

    class Service:
        async def start(self):
            pass

        async def start_stream(self, **values):
            calls.append(values)
            return SimpleNamespace(session_id="existing", idempotent=True)

        def get_session(self, session_id):
            return SimpleNamespace(playback_token="response-only-token")

        @staticmethod
        def _normalize_supported_codecs(codecs):
            return codecs

    monkeypatch.setattr(live_routes, "live_streaming_service", Service())
    response = await live_routes.start_live_stream(
        "  handofblood  ",
        JsonRequest(
            {
                "quality": "720p",
                "supported_codecs": "h264,h265",
                "enhanced_quality": True,
            }
        ),
        db=Database([streamer]),
        current_user=SimpleNamespace(id=7),
    )

    assert calls == [
        {
            "streamer_name": "HandOfBlood",
            "channel_key": "stable-42",
            "quality": "720p",
            "supported_codecs": "h264,h265",
            "user_id": "7",
            "enhanced_quality": True,
        }
    ]
    assert response == {
        "success": True,
        "session_id": "existing",
        "streamer_name": "HandOfBlood",
        "quality": "720p",
        "supported_codecs": "h264,h265",
        "playlist_url": (
            "/api/live/stream/existing/playlist.m3u8?token=response-only-token"
        ),
        "idempotent": True,
    }


@pytest.mark.asyncio
async def test_start_route_returns_exact_coordinator_conflict(monkeypatch):
    streamer = SimpleNamespace(username="streamer", twitch_id="stable-43")

    class Service:
        async def start(self):
            pass

        async def start_stream(self, **values):
            raise TwitchUpstreamConflict(
                "twitch_upstream_authenticated_budget_exhausted",
                "authenticated_budget_exhausted",
                values["channel_key"],
            )

    monkeypatch.setattr(live_routes, "live_streaming_service", Service())
    with pytest.raises(HTTPException) as raised:
        await live_routes.start_live_stream(
            "streamer",
            JsonRequest({"enhanced_quality": True}),
            db=Database([streamer]),
            current_user=SimpleNamespace(id=7),
        )

    assert raised.value.status_code == 409
    assert raised.value.detail == {
        "code": "twitch_upstream_authenticated_budget_exhausted",
        "reason": "authenticated_budget_exhausted",
        "channel_key": "stable-43",
        "retryable": False,
    }


@pytest.mark.asyncio
async def test_stop_route_rejects_foreign_user_without_stopping(monkeypatch):
    stop_calls = []

    class Service:
        def get_session(self, session_id):
            return SimpleNamespace(user_id="8")

        async def stop_stream(self, session_id, requesting_user_id):
            stop_calls.append((session_id, requesting_user_id))
            raise TwitchUpstreamStopForbidden("not_lease_owner")

    monkeypatch.setattr(live_routes, "live_streaming_service", Service())
    with pytest.raises(HTTPException) as raised:
        await live_routes.stop_live_stream(
            "foreign-session", current_user=SimpleNamespace(id=7)
        )

    assert raised.value.status_code == 403
    assert raised.value.detail == {
        "code": "twitch_upstream_stop_forbidden",
        "reason": "not_lease_owner",
    }
    assert stop_calls == [("foreign-session", "7")]
