"""Real ORM roundtrips for the active catalog's SQLite/UTC compatibility.

PostgreSQL cases opt in via STREAMVAULT_POSTGRES_TEST_URL pointing to a local
streamvault_test_* database; only a uniquely owned schema is created/removed.
"""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from app.database import Base
from app.models import ActiveRecordingState, Recording, Stream, Streamer
from app.services.media.video_catalog_service import VideoCatalogService


NOW = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def catalog_clock(monkeypatch):
    from app.services.media import video_catalog_service

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(video_catalog_service, "datetime", FixedClock)


@pytest.fixture(params=["sqlite", "postgres"])
def catalog_sessions(request, tmp_path):
    schema = None
    if request.param == "sqlite":
        engine = create_engine(
            f"sqlite:///{tmp_path / 'catalog.db'}",
            connect_args={"check_same_thread": False},
        )
    else:
        url = os.environ.get("STREAMVAULT_POSTGRES_TEST_URL")
        if not url:
            pytest.skip("requires isolated STREAMVAULT_POSTGRES_TEST_URL")
        parsed = make_url(url)
        if (
            not parsed.drivername.startswith("postgresql")
            or parsed.host
            not in {"127.0.0.1", "localhost", "::1", "host.docker.internal"}
            or not (parsed.database or "").startswith("streamvault_test_")
        ):
            pytest.fail("catalog tests require a local disposable PostgreSQL database")
        schema = "catalog_" + uuid4().hex
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine.dispose()
        engine = create_engine(
            url,
            connect_args={"options": f"-csearch_path={schema} -ctimezone=Asia/Kolkata"},
        )
    tables = [
        model.__table__ for model in (Streamer, Stream, Recording, ActiveRecordingState)
    ]
    try:
        Base.metadata.create_all(engine, tables=tables)
        yield sessionmaker(bind=engine), request.param
    finally:
        if schema:
            with engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def persist_active(sessions, tmp_path, started):
    """Close the writer so the catalog must reload database timestamps."""
    media = tmp_path / f"{uuid4().hex}.ts"
    media.write_bytes(b"synthetic growing recording")
    with sessions() as db:
        streamer = Streamer(twitch_id=uuid4().hex, username="catalog-test")
        db.add(streamer)
        db.flush()
        stream = Stream(
            streamer_id=streamer.id,
            twitch_stream_id=uuid4().hex,
            title="Active recording",
            started_at=started,
        )
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id, start_time=started, status="recording"
        )
        db.add(recording)
        db.flush()
        state = ActiveRecordingState(
            stream_id=stream.id,
            recording_id=recording.id,
            process_id=12345,
            process_identifier="synthetic-catalog-test",
            streamer_name=streamer.username,
            started_at=started,
            last_heartbeat=started,
            ts_output_path=str(media),
            status="active",
        )
        db.add(state)
        db.commit()
        return stream.id, recording.id, state.id, media


@pytest.mark.parametrize("timestamp_kind", ["utc", "backend_variant"])
def test_active_recording_survives_roundtrip_and_real_get(
    catalog_sessions, tmp_path, timestamp_kind
):
    from app import dependencies
    from app.routes import videos

    sessions, backend = catalog_sessions
    started = NOW - timedelta(minutes=5)
    if timestamp_kind == "backend_variant":
        started = (
            started.replace(tzinfo=None)
            if backend == "sqlite"
            else started.astimezone(timezone(timedelta(hours=5, minutes=30)))
        )
    stream_id, recording_id, state_id, media = persist_active(
        sessions, tmp_path, started
    )
    with sessions() as db:
        reloaded = db.get(ActiveRecordingState, state_id)
        if backend == "sqlite":
            assert reloaded.started_at.tzinfo is None
        else:
            assert reloaded.started_at == started
            assert reloaded.started_at.utcoffset() == timedelta(hours=5, minutes=30)
        service_videos = VideoCatalogService(db).list_all_videos()
        assert len(service_videos) == 1
        assert service_videos[0]["duration"] == 300

    application = FastAPI()
    application.include_router(videos.router)

    def fresh_db():
        with sessions() as db:
            yield db

    application.dependency_overrides[dependencies.get_db] = fresh_db
    application.dependency_overrides[dependencies.get_current_identity] = lambda: (
        dependencies.AuthIdentity(
            subject="catalog-test",
            roles=frozenset(),
            scopes=frozenset(),
            auth_method="legacy-session",
            interactive=True,
        )
    )
    with TestClient(application) as client:
        response = client.get("/api/videos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    video = response.json()[0]
    assert video["id"] == stream_id
    assert video["recording_id"] == recording_id
    assert video["is_recording"] is True
    assert video["duration"] == 300
    assert video["file_path"] == str(media)
    assert video["file_size"] == media.stat().st_size
    assert video["ended_at"] is None
    with sessions() as db:
        assert db.get(ActiveRecordingState, state_id).status == "active"


@pytest.mark.parametrize("missing", ["state", "both", "malformed"])
def test_active_timestamp_fallback_and_entry_isolation(
    catalog_sessions, tmp_path, missing, caplog
):
    sessions, _ = catalog_sessions
    started = NOW - timedelta(minutes=5)
    good_id, _, _, _ = persist_active(sessions, tmp_path, started)
    other_id, recording_id, state_id, _ = persist_active(sessions, tmp_path, started)
    with sessions() as db:
        # Model columns are NOT NULL. Inject legacy/malformed values only after
        # a real read, without fake query results or persisting invalid rows.
        state = db.get(ActiveRecordingState, state_id)
        stream = db.get(Stream, other_id)
        set_committed_value(
            state, "started_at", "invalid" if missing == "malformed" else None
        )
        if missing == "both":
            set_committed_value(stream, "started_at", None)
        videos = {
            video["id"]: video for video in VideoCatalogService(db).list_all_videos()
        }
    assert videos[good_id]["is_recording"] is True
    assert videos[good_id]["duration"] == 300
    if missing == "malformed":
        assert other_id not in videos
        assert f"Error surfacing active recording {recording_id}" in caplog.text
    elif missing == "both":
        assert videos[other_id]["duration"] is None
        assert videos[other_id]["started_at"] is None
    else:
        assert videos[other_id]["duration"] == 300


@pytest.mark.parametrize("source", ["stream", "recording"])
def test_finished_catalog_and_active_dedupe_remain_unchanged(
    catalog_sessions, tmp_path, source
):
    sessions, _ = catalog_sessions
    started = NOW - timedelta(minutes=5)
    stream_id, recording_id, _, media = persist_active(sessions, tmp_path, started)
    with sessions() as db:
        stream = db.get(Stream, stream_id)
        stream.ended_at = started + timedelta(minutes=2)
        recording = db.get(Recording, recording_id)
        recording.status = "completed"
        recording.path = str(media)
        recording.end_time = started + timedelta(minutes=2)
        if source == "stream":
            stream.recording_path = str(media)
        db.commit()
    with sessions() as db:
        catalog = VideoCatalogService(db)
        videos = catalog.list_all_videos()
        assert len(videos) == 1
        assert videos[0]["id"] == stream_id
        assert videos[0]["duration"] == 120
        assert not videos[0].get("is_recording", False)
        streamer_videos = catalog.list_for_streamer(
            db.get(Stream, stream_id).streamer_id
        )
        assert len(streamer_videos) == 1
        assert streamer_videos[0]["duration"] == 120
