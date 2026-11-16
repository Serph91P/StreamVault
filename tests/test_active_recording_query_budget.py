"""Actual DB query counts and eventloop/session affinity on cache misses."""

import asyncio
from datetime import datetime, timedelta, timezone
import threading
import time

import pytest
from sqlalchemy import event

from app.database import Base
from app.models import Recording, Stream, Streamer
from app.routes import recording
from app.utils.cache import app_cache
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


@pytest.mark.asyncio
async def test_active_recordings_batch_queries_and_keep_db_off_eventloop(
    catalog_sessions, monkeypatch
):
    sessions, _ = catalog_sessions
    engine = sessions.kw["bind"]
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        for n in range(10):
            streamer = Streamer(twitch_id=f"active-{n}", username=f"active-{n}")
            db.add(streamer)
            db.flush()
            stream = Stream(
                streamer_id=streamer.id,
                title=f"active {n}",
                started_at=now - timedelta(minutes=5),
            )
            db.add(stream)
            db.flush()
            db.add(
                Recording(
                    stream_id=stream.id,
                    start_time=stream.started_at,
                    status="recording",
                )
            )
        db.commit()
    monkeypatch.setattr(recording, "SessionLocal", sessions)
    app_cache.delete("active_recordings")
    app_cache.delete("active_recordings_fallback")
    query_threads = []
    main_thread = threading.get_ident()
    ticks = 0
    done = False

    def delay_and_count(*_):
        query_threads.append(threading.get_ident())
        time.sleep(0.02)

    async def heartbeat():
        nonlocal ticks
        while not done:
            ticks += 1
            await asyncio.sleep(0.005)

    event.listen(engine, "before_cursor_execute", delay_and_count)
    ticker = asyncio.create_task(heartbeat())
    try:
        result = await recording.get_active_recordings(
            session_factory=sessions, status_cache=app_cache
        )
        assert len(query_threads) <= 3, (
            "active response must not query settings/lease per recording"
        )
        assert len(result) == 10, (
            "SQLite naive UTC must not drop healthy active recordings"
        )
        assert all(thread != main_thread for thread in query_threads)
        assert ticks >= 3, "database latency blocked the eventloop heartbeat"
        for item in result:
            assert isinstance(item, dict)
            assert 299 <= item["duration"] <= 310
            assert item["twitch_auth_priority"] == 0
            assert item["effective_auth_mode"] == "unknown"
    finally:
        done = True
        await ticker
        event.remove(engine, "before_cursor_execute", delay_and_count)
        app_cache.delete("active_recordings")
        app_cache.delete("active_recordings_fallback")
