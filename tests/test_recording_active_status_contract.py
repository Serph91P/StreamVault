"""Synthetic route-level contract coverage for the recording status consumer."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Recording,
    Stream,
    Streamer,
    StreamerRecordingSettings,
    TwitchUpstreamLease,
)
from app.routes import recording as recording_routes


class _MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object, ttl: int | None = None) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class _NaiveUtcClock:
    """Keeps SQLite's naive test timestamps compatible with the route clock."""

    @staticmethod
    def now(_timezone=None):
        return datetime.now(timezone.utc).replace(tzinfo=None)


def _lease(recording_id: int, channel_key: str, *, state: str, auth_key: str | None,
           handoff_reason: str, partial_warning: bool) -> TwitchUpstreamLease:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TwitchUpstreamLease(
        channel_key=channel_key,
        recording_id=recording_id,
        purpose="RECORDING",
        state=state,
        generation=1,
        auth_key=auth_key,
        auth_requested=True,
        anonymous_available=True,
        handoff_reason=handoff_reason,
        partial_recording_warning=partial_warning,
        reserved_at=now,
        heartbeat_at=now,
        expires_at=now + timedelta(minutes=5),
        created_at=now,
        updated_at=now,
    )


def test_active_recordings_route_exposes_persisted_auth_handoff_contract(monkeypatch):
    """Route output preserves synthetic persisted state for the frontend seam."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables = [
        Streamer.__table__,
        Stream.__table__,
        Recording.__table__,
        StreamerRecordingSettings.__table__,
        TwitchUpstreamLease.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    cache = _MemoryCache()
    monkeypatch.setattr(recording_routes, "SessionLocal", Session)

    # The route imports this module inside the handler, so replace its cache value
    # rather than calling a service or a frontend mock.
    from app.utils import cache as cache_module

    monkeypatch.setattr(cache_module, "app_cache", cache)

    with Session() as db:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        pending_streamer = Streamer(twitch_id="pending-id", username="pending-channel")
        blocked_streamer = Streamer(twitch_id="blocked-id", username="blocked-channel")
        db.add_all([pending_streamer, blocked_streamer])
        db.flush()
        db.add_all([
            StreamerRecordingSettings(
                streamer_id=pending_streamer.id, twitch_auth_priority=-25
            ),
            StreamerRecordingSettings(
                streamer_id=blocked_streamer.id, twitch_auth_priority=17
            ),
        ])
        pending_stream = Stream(
            streamer_id=pending_streamer.id,
            title="Pending recording",
            twitch_stream_id="pending-stream",
            started_at=now,
        )
        blocked_stream = Stream(
            streamer_id=blocked_streamer.id,
            title="Blocked recording",
            twitch_stream_id="blocked-stream",
            started_at=now,
        )
        db.add_all([pending_stream, blocked_stream])
        db.flush()
        pending_recording = Recording(
            stream_id=pending_stream.id,
            start_time=now,
            status="recording",
            path="/synthetic/pending.ts",
        )
        blocked_recording = Recording(
            stream_id=blocked_stream.id,
            start_time=now,
            status="recording",
            path="/synthetic/blocked.ts",
        )
        db.add_all([pending_recording, blocked_recording])
        db.flush()
        db.add_all([
            _lease(
                pending_recording.id,
                "pending-channel",
                state="ROTATING",
                auth_key="synthetic-auth-key",
                handoff_reason="awaiting_higher_priority_handoff",
                partial_warning=True,
            ),
            _lease(
                blocked_recording.id,
                "blocked-channel",
                state="ACTIVE",
                auth_key=None,
                handoff_reason="live_playback_owner_not_preemptible",
                partial_warning=False,
            ),
        ])
        db.commit()

    application = FastAPI()
    application.include_router(recording_routes.router)
    monkeypatch.setattr(recording_routes, "datetime", _NaiveUtcClock)
    with TestClient(application) as client:
        response = client.get("/api/recording/active")

    assert response.status_code == 200
    fixture_path = Path(__file__).resolve().parents[1] / "app/frontend/tests/fixtures/recording-active-status-contract.json"
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    portable_fields = (
        "streamer_name", "title", "file_path", "status", "duration",
        "twitch_auth_priority", "effective_auth_mode", "pending_handoff",
        "handoff_reason", "partial_recording_warning",
    )
    actual_by_streamer = {item["streamer_name"]: item for item in response.json()}
    expected_by_streamer = {item["streamer_name"]: item for item in expected}

    # This fixture is consumed unchanged by the frontend facade test. Route ids
    # and timestamps are generated by SQLite, so compare the portable B2 wire
    # contract that crosses the backend/frontend boundary.
    assert {
        streamer: {field: actual_by_streamer[streamer][field] for field in portable_fields}
        for streamer in expected_by_streamer
    } == {
        streamer: {field: expected_by_streamer[streamer][field] for field in portable_fields}
        for streamer in expected_by_streamer
    }
    engine.dispose()
