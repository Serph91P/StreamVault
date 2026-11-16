"""Cleanup save/readback contract, using actual routes and disposable SQLite."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Streamer, StreamerRecordingSettings
from app.routes import recording


@pytest.mark.asyncio
async def test_channel_cleanup_readback_preserves_saved_inheritance(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(recording, "SessionLocal", sessions)
    monkeypatch.setattr(
        recording.unified_image_service, "get_profile_image_url", lambda *_: None
    )
    policy = {
        "type": "age",
        "threshold": 37,
        "preserve_favorites": False,
        "preserve_categories": [],
    }
    try:
        with sessions() as db:
            db.add(
                Streamer(
                    id=947,
                    twitch_id="synthetic-947",
                    username="synthetic-policy",
                    auto_record=False,
                )
            )
            db.add(
                StreamerRecordingSettings(
                    streamer_id=947, enabled=False, use_global_cleanup_policy=True
                )
            )
            db.commit()
            for inherits in (False, True):
                recording.update_streamer_cleanup_policy(
                    947,
                    {"cleanup_policy": policy, "use_global_cleanup_policy": inherits},
                    db,
                )
                response = recording.get_all_streamer_recording_settings(
                    session_factory=sessions,
                    unified_image_service=recording.unified_image_service,
                )[0]
                assert response.use_global_cleanup_policy is inherits
                with sessions() as readback:
                    stored = readback.query(StreamerRecordingSettings).one()
                    assert stored.use_global_cleanup_policy is inherits
                    assert (
                        json.loads(stored.cleanup_policy)
                        if stored.cleanup_policy
                        else None
                    ) == (None if inherits else {**policy, "preserve_timeframe": None})
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("raw_flag", "expected_status", "stored_flag"),
    [
        (None, 200, None),
        (0, 200, False),
        (1, 200, True),
        (False, 200, False),
        (True, 200, True),
        (2, 500, True),
        ("false", 500, True),
        ({}, 500, True),
        ([], 500, True),
    ],
)
def test_cleanup_policy_raw_flag_keeps_sql_boolean_validation(
    raw_flag, expected_status, stored_flag
):
    """Typing must not coerce raw JSON or move legacy SQL validation to 422."""
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    app = FastAPI()
    app.include_router(recording.router)

    def database():
        with sessions() as db:
            yield db

    app.dependency_overrides[recording.get_db] = database
    try:
        with sessions() as db:
            db.add(
                Streamer(
                    id=947,
                    twitch_id="synthetic-947",
                    username="synthetic-policy",
                    auto_record=False,
                )
            )
            db.add(
                StreamerRecordingSettings(
                    streamer_id=947, enabled=False, use_global_cleanup_policy=True
                )
            )
            db.commit()
        with TestClient(app) as client:
            response = client.post(
                "/api/recording/streamers/947/cleanup-policy",
                json={"use_global_cleanup_policy": raw_flag},
            )
        assert response.status_code == expected_status
        with sessions() as db:
            assert (
                db.query(StreamerRecordingSettings).one().use_global_cleanup_policy
                is stored_flag
            )
    finally:
        engine.dispose()
