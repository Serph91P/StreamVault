"""Required-file failures must preserve the real catalog/retry target (#953)."""

import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Recording, Stream, Streamer, StreamMetadata
from app.services.system.cleanup_service import CleanupService


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    import app.config.settings as config

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: SimpleNamespace(
            RECORDING_DIRECTORY=str(tmp_path / "synthetic953"),
        ),
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(connection)
    directory = tmp_path / "synthetic953" / "Season 2026"
    directory.mkdir(parents=True)
    media, sidecar = directory / "episode.mp4", directory / "episode.nfo"
    media.write_bytes(b"synthetic completed media")
    sidecar.write_bytes(b"synthetic per-stream metadata")
    with Session(engine) as db:
        streamer = Streamer(username="synthetic953", twitch_id="synthetic953")
        db.add(streamer)
        db.flush()
        started = datetime.now(timezone.utc) - timedelta(days=10)
        stream = Stream(
            streamer_id=streamer.id,
            title="completed",
            started_at=started,
            ended_at=started + timedelta(hours=1),
            recording_path=str(media),
        )
        db.add(stream)
        db.flush()
        recording = Recording(
            stream_id=stream.id, path=str(media), status="completed", start_time=started
        )
        metadata = StreamMetadata(stream_id=stream.id, nfo_path=str(sidecar))
        db.add_all([recording, metadata])
        db.commit()
        yield db, stream, recording.id, metadata.id, media, sidecar
    engine.dispose()


def snapshot(db):
    return {
        table.name: list(db.execute(select(table)).tuples())
        for table in Base.metadata.sorted_tables
    }


@pytest.mark.asyncio
async def test_retention_preserves_outside_root_catalog_and_bytes(catalog):
    db, stream, recording_id, metadata_id, media, sidecar = catalog
    outside = media.parent.parent.parent / "outside.mp4"
    outside.write_bytes(b"outside permitted recording root")
    stream.recording_path = str(outside)
    db.get(Recording, recording_id).path = str(outside)
    db.commit()
    before = snapshot(db)
    count, _ = await CleanupService._delete_streams([stream], db)
    assert count == 0
    assert outside.read_bytes() == b"outside permitted recording root"
    db.expire_all()
    assert snapshot(db) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "permission",
        "io",
        "sidecar",
        "noop",
        "segments",
        "segments_noop",
        "recording_path",
    ],
)
async def test_retention_failure_retains_catalog_then_retries(
    catalog, monkeypatch, failure
):
    db, stream, recording_id, metadata_id, media, sidecar = catalog
    stream_id = stream.id
    blocked = sidecar if failure == "sidecar" else media
    segments = media.with_name("episode_segments")
    if failure.startswith("segments"):
        segments.mkdir()
        (segments / "segment_001.ts").write_bytes(b"synthetic segment")
        blocked = segments
    if failure == "recording_path":
        stream.recording_path = None
        db.commit()
    before = snapshot(db)
    original_remove, original_rmtree = os.remove, shutil.rmtree

    def remove(path, *args, **kwargs):
        if Path(path) == blocked:
            if failure == "noop":
                return None
            if failure == "io":
                raise OSError("synthetic transient I/O error")
            raise PermissionError("synthetic read-only mount")
        return original_remove(path, *args, **kwargs)

    def rmtree(path, *args, **kwargs):
        if Path(path) == blocked:
            if failure == "segments_noop":
                return None
            raise PermissionError("synthetic read-only segment directory")
        return original_rmtree(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(os, "remove", remove)
        patch.setattr(shutil, "rmtree", rmtree)
        count, deleted = await CleanupService._delete_streams([stream], db)
    assert count == 0
    assert str(blocked) not in deleted
    assert blocked.exists()
    db.expire_all()
    assert snapshot(db) == before
    assert db.get(Recording, recording_id) is not None
    assert db.get(StreamMetadata, metadata_id) is not None

    retry_count, _ = await CleanupService._delete_streams(
        [db.get(Stream, stream_id)], db
    )
    assert retry_count == 1
    db.expire_all()
    assert db.get(Stream, stream_id) is None
    assert db.get(Recording, recording_id) is None
    assert db.get(StreamMetadata, metadata_id) is None
    assert not os.path.lexists(media)
    assert not sidecar.exists()
    assert not segments.exists()
    assert await CleanupService._delete_streams([], db) == (0, [])


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["missing", "broken_symlink", "mkv"])
async def test_retention_verifies_absence_and_is_idempotent(catalog, state):
    db, stream, recording_id, metadata_id, media, sidecar = catalog
    stream_id = stream.id
    if state == "mkv":
        renamed = media.with_suffix(".mkv")
        media.rename(renamed)
        media = renamed
        stream.recording_path = str(media)
        db.get(Recording, recording_id).path = str(media)
        db.commit()
    else:
        media.unlink()
    if state == "broken_symlink":
        media.symlink_to(media.with_name("absent-target.mp4"))
    count, deleted = await CleanupService._delete_streams([stream], db)
    assert count == 1
    assert len(deleted) == len(set(deleted))
    assert not os.path.lexists(media)
    assert not sidecar.exists()
    db.expire_all()
    assert db.get(Stream, stream_id) is None
    assert db.get(Recording, recording_id) is None
    assert db.get(StreamMetadata, metadata_id) is None
    assert await CleanupService._delete_streams([], db) == (0, [])
