"""SQL catalog paging and reconciliation with actual SQLite/PostgreSQL rows."""

import asyncio
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event

from app import dependencies
from app.database import Base
from app.models import Recording, Stream, Streamer
from app.routes import videos
from app.services.media.video_catalog_service import VideoCatalogService
from test_video_catalog_timestamps import catalog_sessions as _catalog_sessions

catalog_sessions = _catalog_sessions


@pytest.mark.parametrize("sort", ["date", "title", "streamer", "duration", "size"])
def test_sql_catalog_page_is_bounded_stable_and_uses_global_totals(
    catalog_sessions, monkeypatch, tmp_path, sort
):
    sessions, _ = catalog_sessions
    engine = sessions.kw["bind"]
    Base.metadata.create_all(engine)
    now = datetime.now(timezone.utc)
    with sessions() as db:
        for n in range(6):
            channel = Streamer(username=f"channel-{n}", twitch_id=f"channel-{n}")
            db.add(channel)
            db.flush()
            for k in range(6):
                media = tmp_path / f"{n}-{k}.mp4"
                media.write_bytes(b"media" * (k + 1))
                db.add(
                    Stream(
                        streamer_id=channel.id,
                        title=f"Video {k}",
                        category_name=f"category-{k % 2}",
                        started_at=now - timedelta(minutes=k),
                        ended_at=now,
                        recording_path=str(media),
                    )
                )
        db.commit()
        assert hasattr(VideoCatalogService, "reconcile_batch"), (
            "catalog needs a bounded persisted metadata backfill"
        )
        cursor, processed = VideoCatalogService(db).reconcile_batch(
            after_id=0, limit=100
        )
        assert processed == 36 and cursor == 36
    app = FastAPI()
    app.include_router(videos.router)
    monkeypatch.setattr(videos, "SessionLocal", sessions, raising=False)
    app.dependency_overrides[dependencies.get_current_identity] = lambda: (
        dependencies.AuthIdentity(
            subject="synthetic-catalog",
            roles=frozenset(),
            scopes=frozenset(),
            auth_method="legacy-session",
            interactive=True,
        )
    )
    statements = []

    def count(_conn, _cursor, statement, *_):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        with TestClient(app) as client:
            first = client.get(
                "/api/videos/catalog", params={"page_size": 5, "sort": sort}
            )
            second = client.get(
                "/api/videos/catalog", params={"page_size": 5, "page": 2, "sort": sort}
            )
            assert first.status_code == second.status_code == 200
            page1, page2 = first.json(), second.json()
            assert len(page1["items"]) == len(page2["items"]) == 5
            assert page1["total"] == page2["total"] == 36
            assert page1["has_more"] is True
            assert page1["index"]["pending"] == 0
            assert page1["summary"]["total"] == 36
            assert len(page1["summary"]["streamers"]) == 6
            assert {item["id"] for item in page1["items"]}.isdisjoint(
                item["id"] for item in page2["items"]
            )
            assert client.get("/api/videos/catalog?page_size=10000").status_code == 422
            assert client.get("/api/videos/catalog?sort=unsafe").status_code == 422
            assert client.get("/api/videos/catalog?page=0").status_code == 422
            named = client.get("/api/videos/catalog?streamer=channel-5").json()
            assert named["total"] == 6
            assert all(item["streamer_name"] == "channel-5" for item in named["items"])
            empty = client.get("/api/videos/catalog?q=does-not-exist").json()
            assert empty["total"] == 0 and empty["items"] == []
            literal = client.get("/api/videos/catalog?q=%25").json()
            assert literal["items"] == []
        limited = [
            sql
            for sql in statements
            if "LIMIT" in sql.upper() and "catalog" in sql.lower()
        ]
        assert len(limited) >= 2, (
            "pagination must limit in SQL, not slice materialized rows"
        )
    finally:
        event.remove(engine, "before_cursor_execute", count)


@pytest.mark.asyncio
async def test_background_backfill_completes_and_drains_on_cancel(
    catalog_sessions, monkeypatch, tmp_path
):
    from app.models import VideoCatalogEntry

    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    media = tmp_path / "backfill.mp4"
    media.write_bytes(b"media")
    with sessions() as db:
        channel = Streamer(username="backfill", twitch_id="backfill")
        db.add(channel)
        db.flush()
        stream = Stream(
            streamer_id=channel.id, title="backfill", recording_path=str(media)
        )
        db.add(stream)
        db.commit()
        stream_id = stream.id
    lifecycle = importlib.import_module("app.lifespan")
    monkeypatch.setattr(lifecycle, "SessionLocal", sessions)
    assert hasattr(lifecycle, "_run_catalog_reconciliation"), (
        "backfill must run outside request handlers"
    )
    task = asyncio.create_task(lifecycle._run_catalog_reconciliation())
    try:
        async with asyncio.timeout(5):
            while True:
                with sessions() as db:
                    entry = db.get(VideoCatalogEntry, stream_id)
                    if entry is not None and entry.state == "available":
                        break
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_catalog_source_changes_invalidate_snapshot_in_same_transaction(
    catalog_sessions, tmp_path
):
    from app.models import VideoCatalogEntry

    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    media = tmp_path / "original.mp4"
    media.write_bytes(b"media")
    with sessions() as db:
        channel = Streamer(username="changed", twitch_id="changed")
        db.add(channel)
        db.flush()
        stream = Stream(
            streamer_id=channel.id, title="before", recording_path=str(media)
        )
        db.add(stream)
        db.commit()
        VideoCatalogService(db).reconcile_batch(after_id=0, limit=100)
        assert hasattr(VideoCatalogService, "track_changes"), (
            "source mutations must invalidate metadata transactionally"
        )
        with VideoCatalogService.track_changes():
            stream.title = "after"
            db.commit()
        db.expire_all()
        assert db.get(VideoCatalogEntry, stream.id).state == "available"
        pending_page = VideoCatalogService(db).list_page()
        assert len(pending_page["items"]) == 1
        assert pending_page["index"]["pending"] == 1
        VideoCatalogService(db).reconcile_batch(after_id=0, limit=100)
        assert VideoCatalogService(db).list_page()["items"][0]["title"] == "after"


def test_reconciliation_does_not_overwrite_newer_source_invalidation(
    catalog_sessions, monkeypatch, tmp_path
):
    from sqlalchemy.orm.exc import StaleDataError

    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    media = tmp_path / "racing.mp4"
    media.write_bytes(b"media")
    with sessions() as db:
        channel = Streamer(username="racing", twitch_id="racing")
        db.add(channel)
        db.flush()
        stream = Stream(
            streamer_id=channel.id, title="original", recording_path=str(media)
        )
        db.add(stream)
        db.commit()
        stream_id = stream.id
        service = VideoCatalogService(db)
        service.reconcile_batch(limit=100)
        with VideoCatalogService.track_changes():
            stream.title = "first mutation"
            db.commit()
            native = type(media).stat
            changed = False

            def mutate_during_stat(path, *args, **kwargs):
                nonlocal changed
                if path == media and not changed:
                    changed = True
                    with sessions() as writer:
                        writer.get(Stream, stream_id).title = "second mutation"
                        writer.commit()
                return native(path, *args, **kwargs)

            monkeypatch.setattr(type(media), "stat", mutate_during_stat)
            with pytest.raises(StaleDataError):
                service.reconcile_batch(limit=100)
            db.rollback()
        assert VideoCatalogService(db).list_page()["index"]["pending"] == 1


def test_heartbeat_only_update_does_not_hide_active_catalog_entry(
    catalog_sessions, tmp_path
):
    from app.models import ActiveRecordingState
    from test_video_catalog_timestamps import persist_active

    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    now = datetime.now(timezone.utc)
    stream_id, _, state_id, _ = persist_active(
        sessions, tmp_path, now - timedelta(minutes=5)
    )
    with sessions() as db:
        VideoCatalogService(db).reconcile_batch(limit=100)
        assert VideoCatalogService(db).list_page(recording=True)["total"] == 1
        with VideoCatalogService.track_changes():
            db.get(ActiveRecordingState, state_id).last_heartbeat = now
            db.commit()
    with sessions() as db:
        page = VideoCatalogService(db).list_page(recording=True)
        assert [item["id"] for item in page["items"]] == [stream_id]
        assert page["index"]["pending"] == 0


@pytest.mark.parametrize("page,remove_index", [(1, 0), (2, 3)])
@pytest.mark.parametrize("streamer_filter", [None, "refill"])
@pytest.mark.parametrize("failure", ["missing", "permission"])
def test_external_delete_refills_page_without_hiding_remaining_videos(
    catalog_sessions,
    tmp_path,
    monkeypatch,
    page,
    remove_index,
    streamer_filter,
    failure,
):
    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    paths = []
    with sessions() as db:
        channel = Streamer(username="refill", twitch_id="refill")
        db.add(channel)
        db.flush()
        for n in range(7):
            media = tmp_path / f"{n}.mp4"
            media.write_bytes(b"media")
            paths.append(media)
            db.add(
                Stream(
                    streamer_id=channel.id,
                    title=f"Video {n}",
                    recording_path=str(media),
                )
            )
        if streamer_filter:
            other = Streamer(username="not-refill", twitch_id="not-refill")
            db.add(other)
            db.flush()
            media = tmp_path / "other.mp4"
            media.write_bytes(b"other channel")
            db.add(
                Stream(
                    streamer_id=other.id,
                    title="Video 0 other",
                    recording_path=str(media),
                )
            )
        db.commit()
        service = VideoCatalogService(db)
        service.reconcile_batch(limit=100)
        if failure == "missing":
            paths[remove_index].unlink()
        else:
            native_stat = Path.stat

            def permission_error(path, *args, **kwargs):
                if path == paths[remove_index]:
                    raise PermissionError("synthetic unavailable storage")
                return native_stat(path, *args, **kwargs)

            monkeypatch.setattr(Path, "stat", permission_error)
        result = service.list_page(
            page=page, page_size=3, sort="title", streamer=streamer_filter
        )
        assert len(result["items"]) == 3
        assert result["total"] == 6
        assert all(item["streamer_name"] == "refill" for item in result["items"])
        assert result["summary"]["total"] == (7 if streamer_filter else 6)
        assert result["has_more"] is (page == 1)
        if page == 2:
            assert [item["id"] for item in result["items"]] == [5, 6, 7]
        else:
            assert [item["id"] for item in result["items"]] == [2, 3, 4]


def test_reconcile_legacy_recording_fallback_and_missing_file_are_honest(
    catalog_sessions, tmp_path
):
    sessions, _ = catalog_sessions
    Base.metadata.create_all(sessions.kw["bind"])
    now = datetime.now(timezone.utc)
    media = tmp_path / "fallback.ts"
    media.write_bytes(b"preserved source")
    with sessions() as db:
        streamer = Streamer(username="fallback", twitch_id="fallback")
        db.add(streamer)
        db.flush()
        stream = Stream(
            streamer_id=streamer.id, title="fallback", started_at=now, ended_at=now
        )
        db.add(stream)
        db.flush()
        db.add(
            Recording(
                stream_id=stream.id,
                status="completed",
                path=str(media),
                start_time=now,
                end_time=now,
            )
        )
        db.commit()
        service = VideoCatalogService(db)
        assert hasattr(service, "reconcile_batch")
        service.reconcile_batch(after_id=0, limit=100)
        page = service.list_page(page=1, page_size=50)
        assert page["total"] == 1
        assert page["items"][0]["file_path"] == str(media)
        assert stream.recording_path is None, (
            "readmodel must not repair authoritative stream paths on GET"
        )
        media.unlink()
        service.reconcile_batch(after_id=0, limit=100)
        page = service.list_page(page=1, page_size=50)
        assert page["total"] == 0
        assert page["index"]["missing"] == 1
