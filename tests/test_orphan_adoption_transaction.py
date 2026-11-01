"""Real mapped Stream/Recording adoption and atomic failure regression (#957)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.database import Base
from app.models import Recording, Stream, Streamer
from app.services.recording.unified_recovery_service import UnifiedRecoveryService


@pytest.fixture
def adoption(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Streamer(username="synthetic", twitch_id="synthetic-957"))
        db.commit()
        directory = tmp_path / "recordings" / "synthetic" / "Season 2026"
        directory.mkdir(parents=True)
        yield UnifiedRecoveryService(), db, directory
    engine.dispose()


def media_file(directory: Path, filename: str) -> Path:
    path = directory / filename
    path.write_bytes(b"synthetic original media bytes")
    return path


@pytest.mark.parametrize(
    "filename",
    ["synthetic - S202601E19 - 2026-01-08T22-00-00.ts", "synthetic_orphan.ts"],
)
def test_adoption_commits_offline_stream_and_recording(adoption, filename):
    service, db, directory = adoption
    path = media_file(directory, filename)
    before = datetime.now(timezone.utc)
    recording_id = service._create_recording_from_orphaned_path(db, str(path))
    assert recording_id is not None
    db.expire_all()
    recording = db.get(Recording, recording_id)
    assert recording is not None
    stream = db.get(Stream, recording.stream_id)
    assert stream is not None
    assert not stream.is_live
    assert stream.ended_at is not None
    assert (
        before
        <= stream.ended_at.replace(tzinfo=timezone.utc)
        <= datetime.now(timezone.utc)
    )
    assert recording.path == str(path)
    assert recording.status == "stopped"
    assert recording.start_time == stream.started_at
    if "S202601E19" in filename:
        assert stream.started_at == datetime(2026, 1, 8, 22)
        assert stream.episode_number == 19
    else:
        assert before <= stream.started_at.replace(tzinfo=timezone.utc)
    assert len(db.scalars(select(Stream)).all()) == 1
    assert len(db.scalars(select(Recording)).all()) == 1
    assert path.read_bytes() == b"synthetic original media bytes"


def test_adoption_reuses_matching_offline_stream(adoption):
    service, db, directory = adoption
    original = Stream(
        streamer_id=db.scalar(select(Streamer.id)),
        title="existing",
        started_at=datetime(2026, 1, 8, 22),
        ended_at=datetime(2026, 1, 8, 23),
        episode_number=19,
    )
    db.add(original)
    db.commit()
    path = media_file(directory, "synthetic - S202601E19 - 2026-01-08T22-00-00.ts")
    recording_id = service._create_recording_from_orphaned_path(db, str(path))
    recording = db.get(Recording, recording_id)
    assert recording is not None
    assert recording.stream_id == original.id
    assert len(db.scalars(select(Stream)).all()) == 1
    assert original.ended_at == datetime(2026, 1, 8, 23)


@pytest.mark.parametrize("table", ["streams", "recordings"])
def test_adoption_insert_failure_is_atomic_and_actionable(adoption, table):
    service, db, directory = adoption
    path = media_file(directory, "synthetic - S202601E19 - 2026-01-08T22-00-00.ts")
    engine = db.get_bind()
    reached = []

    def reject_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith(f"INSERT INTO {table} "):
            reached.append(table)
            raise SQLAlchemyError("synthetic insertion failure")

    event.listen(engine, "before_cursor_execute", reject_insert)
    try:
        with pytest.raises(DomainError) as error:
            service._create_recording_from_orphaned_path(db, str(path))
        assert error.value.code == "recovery_adoption_failed"
        assert "retry" in error.value.message.lower()
    finally:
        event.remove(engine, "before_cursor_execute", reject_insert)
    assert reached == [table]
    assert db.scalars(select(Stream)).all() == []
    assert db.scalars(select(Recording)).all() == []
    assert path.read_bytes() == b"synthetic original media bytes"
    # The rolled-back session remains usable for the same operation's retry.
    assert service._create_recording_from_orphaned_path(db, str(path)) is not None
    assert len(db.scalars(select(Stream)).all()) == 1
    assert len(db.scalars(select(Recording)).all()) == 1


def test_unidentified_streamer_does_not_create_rows(adoption):
    service, db, directory = adoption
    unknown = directory.parent.parent / "unknown"
    unknown.mkdir()
    path = media_file(unknown, "unknown.ts")
    assert service._create_recording_from_orphaned_path(db, str(path)) is None
    assert db.scalars(select(Stream)).all() == []
    assert db.scalars(select(Recording)).all() == []
