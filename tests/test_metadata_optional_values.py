"""Nullable legacy model values retain their existing success/failure contract."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.database import Base, DatabaseLifecycle
from app.models import RecordingSettings, Stream, Streamer, StreamEvent, StreamMetadata
from app.services.media.metadata_service import MetadataService


@pytest.mark.parametrize(
    "case", ["undated-season", "undated-flat", "null-preset", "null-event", "no-events"]
)
def test_nullable_metadata_controls(tmp_path, case):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'optional.db'}")
    service = MetadataService(session_factory=database.sync_session_factory)
    directory = tmp_path / "alice"
    if case == "undated-season":
        directory /= "Season 2026-11"
    directory.mkdir(parents=True)
    started = (
        None
        if case.startswith("undated")
        else datetime(2026, 11, 1, tzinfo=timezone.utc)
    )
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            streamer = Streamer(id=1, username="alice", twitch_id="alice")
            session.add(streamer)
            session.flush()
            stream = Stream(
                id=1,
                streamer_id=1,
                started_at=started,
                ended_at=started + timedelta(minutes=5) if started else None,
                category_name="Game",
                title="Recording",
            )
            session.add(stream)
            session.flush()
            metadata = StreamMetadata(stream_id=1)
            session.add(metadata)
            session.flush()
            if case.startswith("undated"):
                assert service.generate_nfo_file(
                    session, stream, streamer, directory, "episode", metadata
                ) is (case == "undated-flat")
            elif case == "null-preset":
                session.add(RecordingSettings(id=1))
                session.flush()
                session.execute(update(RecordingSettings).values(filename_preset=None))
                session.expire_all()
                assert (
                    service._create_media_server_specific_files(
                        stream, directory, db=session, streamer=streamer
                    )
                    is False
                )
            elif case == "null-event":
                assert (
                    service._generate_vtt_chapters(
                        stream,
                        [StreamEvent(timestamp=None, title="Malformed")],
                        directory / "episode.vtt",
                    )
                    is False
                )
            else:
                output = directory / "episode-ffmpeg-chapters.txt"
                assert service._generate_ffmpeg_chapters(stream, [], output)
                assert output.read_text().count("[CHAPTER]") == 1
                assert (
                    session.scalar(select(func.count()).select_from(StreamEvent)) == 0
                )
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        database.sync_engine.dispose()
