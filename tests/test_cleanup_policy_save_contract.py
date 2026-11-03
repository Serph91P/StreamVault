"""Cleanup save/readback contract, using actual routes and disposable SQLite."""

import json

import pytest
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
                await recording.update_streamer_cleanup_policy(
                    947,
                    {"cleanup_policy": policy, "use_global_cleanup_policy": inherits},
                    db,
                )
                response = (await recording.get_all_streamer_recording_settings())[0]
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
