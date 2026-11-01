"""Chapter generation keeps models, persistence and file work in one worker."""

import asyncio
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
async def test_chapter_generation_uses_owned_closed_off_loop_scopes(
    tmp_path, monkeypatch
):
    databases = [
        DatabaseLifecycle(f"sqlite:///{tmp_path / (name + '.db')}")
        for name in ("first", "second")
    ]
    services = []
    queries = []
    writes = []
    loop_thread = get_ident()
    started_at = datetime(2026, 10, 1, tzinfo=timezone.utc)
    native_open = builtins.open

    def open_file(path, *args, **kwargs):
        if isinstance(path, (str, bytes)) or hasattr(path, "__fspath__"):
            text = str(path)
            if text.startswith(str(tmp_path)) and text.endswith(
                (".vtt", ".srt", ".xml", "-ffmpeg-chapters.txt")
            ):
                writes.append(get_ident())
        return native_open(path, *args, **kwargs)

    try:
        for index, database in enumerate(databases):
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(Streamer(id=1, username="alice", twitch_id="alice"))
                session.flush()
                session.add(
                    Stream(
                        id=1,
                        streamer_id=1,
                        title=f"title-{index}",
                        category_name=f"category-{index}",
                        started_at=started_at,
                        ended_at=started_at + timedelta(minutes=1),
                    )
                )
                session.flush()
                session.add(StreamMetadata(stream_id=1))
                session.add_all(
                    [
                        StreamEvent(
                            stream_id=1,
                            timestamp=started_at - timedelta(seconds=10),
                            title=f"opening-{index}",
                            category_name=f"category-{index}",
                            event_type="channel.update",
                        ),
                        StreamEvent(
                            stream_id=1,
                            timestamp=started_at + timedelta(seconds=30),
                            title=f"middle-{index}",
                            category_name=f"next-{index}",
                            event_type="channel.update",
                        ),
                    ]
                )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )
            services.append(
                MetadataService(
                    session_factory=lambda database=database: (
                        database.sync_session_factory()
                    )
                )
            )
        assert queries == []
        targets = [
            tmp_path / "alice" / name / "episode.mp4" for name in ("first", "second")
        ]
        for target in targets:
            target.parent.mkdir(parents=True)
        with monkeypatch.context() as watched:
            watched.setattr(builtins, "open", open_file)
            results = await asyncio.gather(
                *(
                    service.ensure_all_chapter_formats(1, str(target))
                    for service, target in zip(services, targets, strict=True)
                )
            )
        operation_queries = queries.copy()
        assert writes and loop_thread not in writes
        assert operation_queries and loop_thread not in operation_queries
        for index, (database, target, result) in enumerate(
            zip(databases, targets, results, strict=True)
        ):
            assert result is not None and set(result) == {"vtt", "srt", "ffmpeg", "xml"}
            for filename in result.values():
                assert target.parent == Path(filename).parent
                text = Path(filename).read_text()
                assert f"category-{index}" in text
                assert f"next-{index}" in text
                assert f"category-{1 - index}" not in text
            assert database.sync_engine.pool.checkedout() == 0
            with database.sync_session_factory() as session:
                metadata = session.scalar(select(StreamMetadata))
                assert metadata.chapters_vtt_path == result["vtt"]
                assert metadata.chapters_srt_path == result["srt"]
                assert metadata.chapters_ffmpeg_path == result["ffmpeg"]
                assert metadata.chapters_xml_path == result["xml"]
            wrong_target = tmp_path / "bob" / f"episode-{index}.mp4"
            wrong_target.parent.mkdir(exist_ok=True)
            assert (
                await services[index].ensure_all_chapter_formats(1, str(wrong_target))
                is None
            )
            assert not list(wrong_target.parent.glob(f"episode-{index}.*"))
    finally:
        for service in services:
            await service.close()
        for database in databases:
            await database.adispose()
