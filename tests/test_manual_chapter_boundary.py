"""Manual chapter ingestion closes its parsing/SQL worker before file generation."""

import builtins
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import get_ident

import pytest
from sqlalchemy import event, select

from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer, StreamEvent, StreamMetadata
from app.services.media.metadata_service import MetadataService


@pytest.mark.asyncio
async def test_manual_import_parses_and_persists_off_loop_without_touching_peer(
    tmp_path, monkeypatch
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'manual.db'}")
    service = MetadataService(session_factory=database.sync_session_factory)
    root = tmp_path / "alice"
    root.mkdir()
    source = root / "manual.txt"
    source.write_text(
        "0:00:00 First chapter\n0:00:30 Second chapter\n", encoding="utf-8"
    )
    queries, reads = [], []
    loop_thread = get_ident()
    original_open = builtins.open

    def opened(path, *args, **kwargs):
        if str(path) == str(source):
            reads.append(get_ident())
        return original_open(path, *args, **kwargs)

    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        started = datetime(2026, 11, 1, tzinfo=timezone.utc)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="alice", twitch_id="alice"))
            session.flush()
            session.add_all(
                [
                    Stream(
                        id=index,
                        streamer_id=1,
                        started_at=started,
                        ended_at=started + timedelta(minutes=2),
                    )
                    for index in (1, 2)
                ]
            )
            session.flush()
            session.add(StreamMetadata(stream_id=1))
            session.add_all(
                [
                    StreamEvent(
                        stream_id=index,
                        timestamp=started,
                        event_type="original",
                        title=f"Original {index}",
                    )
                    for index in (1, 2)
                ]
            )
            session.commit()
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_: queries.append(get_ident()),
        )
        with monkeypatch.context() as observed:
            observed.setattr(builtins, "open", opened)
            result = await service.import_manual_chapters(
                1, str(source), str(root / "episode.mp4")
            )
            await service._create_media_server_chapters(1, str(root / "episode.mp4"))
        assert result is not None and set(result) == {"vtt", "srt", "ffmpeg", "xml"}
        assert queries and loop_thread not in queries
        assert reads and loop_thread not in reads
        plex = (root / "episode.chapters.txt").read_text()
        assert "CHAPTER01NAME=First chapter" in plex
        assert "CHAPTER02NAME=Second chapter" in plex
        for filename in result.values():
            assert "First chapter" in Path(filename).read_text()
            assert "Second chapter" in Path(filename).read_text()
        with database.sync_session_factory() as session:
            imported = list(
                session.scalars(
                    select(StreamEvent)
                    .where(StreamEvent.stream_id == 1)
                    .order_by(StreamEvent.timestamp)
                )
            )
            assert [(item.event_type, item.title) for item in imported] == [
                ("manual.chapter", "First chapter"),
                ("manual.chapter", "Second chapter"),
            ]
            peer = session.scalar(select(StreamEvent).where(StreamEvent.stream_id == 2))
            assert peer.event_type == "original" and peer.title == "Original 2"
        assert source.read_text().endswith("Second chapter\n")
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await service.close()
        await database.adispose()
