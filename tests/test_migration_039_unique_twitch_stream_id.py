"""
Tests for migration 039: unique index on streams.twitch_stream_id.

The stream.online dedup in app/events/handler_registry.py relies on
twitch_stream_id being unique per Stream row; these tests verify the
migration is discovered by the MigrationService, that it merges duplicate
rows correctly, and that the resulting index enforces uniqueness while
still allowing multiple NULLs.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Recording, Stream, StreamEvent, Streamer

MIGRATION_NAME = "039_add_unique_twitch_stream_id.py"
MIGRATION_PATH = Path(__file__).resolve().parents[1] / "migrations" / MIGRATION_NAME


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_039", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db_engine(tmp_path):
    """File-based SQLite engine with the pre-migration schema (no unique index)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'migration_039.db'}", future=True)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # The updated model creates the index as UNIQUE; drop it to recreate
        # the old production schema so duplicate rows can be inserted.
        conn.execute(text("DROP INDEX IF EXISTS ix_streams_twitch_stream_id"))
        conn.execute(
            text(
                "CREATE INDEX ix_streams_twitch_stream_id "
                "ON streams (twitch_stream_id)"
            )
        )
    yield engine
    engine.dispose()


def test_migration_is_registered():
    """The migration file must be discovered by the MigrationService."""
    from app.services.system.migration_service import MigrationService

    scripts = [Path(p).name for p in MigrationService.get_all_migration_scripts()]
    assert MIGRATION_NAME in scripts

    migration = _load_migration()
    # run_migration_script() requires an upgrade() or run_migration() function
    assert hasattr(migration, "upgrade")


def test_model_declares_twitch_stream_id_unique():
    column = Stream.__table__.c.twitch_stream_id
    assert column.unique is True
    assert column.nullable is True


def test_upgrade_merges_duplicates_and_enforces_uniqueness(db_engine):
    started = datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc)
    Session = sessionmaker(bind=db_engine, future=True)

    with Session() as session:
        streamer = Streamer(twitch_id="1000", username="teststreamer")
        session.add(streamer)
        session.flush()

        # Three duplicates of the same Twitch stream: the middle one has a
        # StreamEvent and a Recording attached and must survive, even though
        # another row has a lower id.
        dup_plain = Stream(
            streamer_id=streamer.id,
            twitch_stream_id="42",
            started_at=started,
            ended_at=started,
            recording_path="/recordings/keep-this-path.mp4",
        )
        dup_with_children = Stream(
            streamer_id=streamer.id,
            twitch_stream_id="42",
            started_at=started,
            title="live title",
        )
        dup_late = Stream(streamer_id=streamer.id, twitch_stream_id="42")
        # Multiple NULL twitch_stream_ids must stay valid after the migration
        null_a = Stream(streamer_id=streamer.id, started_at=started)
        null_b = Stream(streamer_id=streamer.id, started_at=started)
        unique_other = Stream(streamer_id=streamer.id, twitch_stream_id="43")
        session.add_all(
            [dup_plain, dup_with_children, dup_late, null_a, null_b, unique_other]
        )
        session.flush()

        session.add(
            StreamEvent(
                stream_id=dup_with_children.id,
                event_type="stream.online",
                timestamp=started,
            )
        )
        session.add(
            Recording(
                stream_id=dup_with_children.id, start_time=started, status="completed"
            )
        )
        # A child row on a doomed duplicate must be repointed to the survivor
        session.add(
            StreamEvent(
                stream_id=dup_plain.id, event_type="channel.update", timestamp=started
            )
        )
        session.commit()
        survivor_id = dup_with_children.id
        merged_ids = {dup_plain.id, dup_late.id}

    migration = _load_migration()
    migration.upgrade(db_engine)

    with Session() as session:
        survivors = session.query(Stream).filter_by(twitch_stream_id="42").all()
        assert [s.id for s in survivors] == [survivor_id]

        # NULL fields on the survivor were filled from the merged duplicates
        assert survivors[0].ended_at is not None
        assert survivors[0].recording_path == "/recordings/keep-this-path.mp4"
        assert survivors[0].title == "live title"

        # All child rows now point at the survivor
        event_stream_ids = {e.stream_id for e in session.query(StreamEvent).all()}
        assert event_stream_ids == {survivor_id}
        recording_stream_ids = {r.stream_id for r in session.query(Recording).all()}
        assert recording_stream_ids == {survivor_id}

        # Duplicates are gone, unrelated rows untouched
        remaining_ids = {s.id for s in session.query(Stream).all()}
        assert not (merged_ids & remaining_ids)
        null_rows = (
            session.query(Stream).filter(Stream.twitch_stream_id.is_(None)).count()
        )
        assert null_rows == 2

    indexes = inspect(db_engine).get_indexes("streams")
    unique_index = next(
        idx for idx in indexes if idx["column_names"] == ["twitch_stream_id"]
    )
    assert unique_index["unique"]

    # The index must actually reject a second row with the same value
    with Session() as session:
        streamer_id = session.query(Streamer).one().id
        session.add(Stream(streamer_id=streamer_id, twitch_stream_id="42"))
        with pytest.raises(IntegrityError):
            session.commit()


def test_upgrade_is_idempotent_and_allows_multiple_nulls(db_engine):
    Session = sessionmaker(bind=db_engine, future=True)
    with Session() as session:
        streamer = Streamer(twitch_id="2000", username="nulltester")
        session.add(streamer)
        session.flush()
        session.add_all(
            [Stream(streamer_id=streamer.id), Stream(streamer_id=streamer.id)]
        )
        session.commit()

    migration = _load_migration()
    migration.upgrade(db_engine)
    # Second run must be a no-op, not an error
    migration.upgrade(db_engine)

    with Session() as session:
        assert session.query(Stream).count() == 2
        # A third NULL row is still allowed under the unique index
        streamer_id = session.query(Streamer).one().id
        session.add(Stream(streamer_id=streamer_id))
        session.commit()
        assert session.query(Stream).count() == 3
