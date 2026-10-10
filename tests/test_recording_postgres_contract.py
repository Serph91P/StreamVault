"""Opt-in FastAPI/PostgreSQL contract coverage for recording settings and status."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import (
    Recording,
    Stream,
    Streamer,
    StreamerRecordingSettings,
    TwitchUpstreamLease,
    User,
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


@pytest.fixture
def recording_application(monkeypatch):
    url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
    if not url:
        pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")

    engine = create_engine(url, future=True)
    tables = [
        User.__table__,
        Streamer.__table__,
        Stream.__table__,
        Recording.__table__,
        StreamerRecordingSettings.__table__,
        TwitchUpstreamLease.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    cache = _MemoryCache()
    application = FastAPI()
    application.include_router(recording_routes.router)

    def override_get_db():
        with Session() as db:
            yield db

    application.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(recording_routes, "SessionLocal", Session)
    from app.utils import cache as cache_module

    monkeypatch.setattr(cache_module, "app_cache", cache)
    try:
        yield application, Session
    finally:
        Base.metadata.drop_all(engine, tables=tables)
        engine.dispose()


def test_postgres_recording_priority_save_round_trips_into_pending_partial_status(
    recording_application,
):
    """The public save and active-status seams preserve a pending handoff."""
    application, Session = recording_application
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with Session() as db:
        streamer = Streamer(twitch_id="postgres-contract-id", username="postgres-contract")
        db.add(streamer)
        db.flush()
        stream = Stream(
            streamer_id=streamer.id,
            title="Synthetic PostgreSQL recording",
            twitch_stream_id="postgres-contract-stream",
            started_at=now,
        )
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id,
            start_time=now,
            status="recording",
            path="/synthetic/postgres-contract.ts",
        )
        db.add(recording)
        db.flush()
        db.add(
            TwitchUpstreamLease(
                channel_key="postgres-contract",
                recording_id=recording.id,
                purpose="RECORDING",
                state="ROTATING",
                generation=1,
                auth_key="synthetic-auth-key",
                auth_requested=True,
                anonymous_available=True,
                handoff_reason="awaiting_higher_priority_handoff",
                partial_recording_warning=True,
                reserved_at=now,
                heartbeat_at=now,
                expires_at=now + timedelta(minutes=5),
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        streamer_id = streamer.id

    with TestClient(application) as client:
        saved = client.post(
            f"/api/recording/streamers/{streamer_id}",
            json={"streamer_id": streamer_id, "enabled": True, "twitch_auth_priority": -25},
        )
        active = client.get("/api/recording/active")

    assert saved.status_code == 200
    assert saved.json()["twitch_auth_priority"] == -25
    assert active.status_code == 200
    assert len(active.json()) == 1
    active_recording = active.json()[0]
    assert active_recording["duration"] == pytest.approx(0, abs=5)
    assert active_recording["started_at"] == now.replace(tzinfo=timezone.utc).isoformat()
    assert {key: value for key, value in active_recording.items() if key not in {"duration", "started_at"}} == {
        "id": 1,
        "stream_id": 1,
        "streamer_id": streamer_id,
        "streamer_name": "postgres-contract",
        "title": "Synthetic PostgreSQL recording",
        "file_path": "/synthetic/postgres-contract.ts",
        "status": "recording",
        "twitch_auth_priority": -25,
        "effective_auth_mode": "authenticated",
        "pending_handoff": True,
        "handoff_reason": "awaiting_higher_priority_handoff",
        "partial_recording_warning": True,
    }
