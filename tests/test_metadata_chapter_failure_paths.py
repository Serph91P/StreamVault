"""Chapter projection/format failure and fallback contracts, with real files."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.models import Stream, StreamEvent
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_metadata_media_server_contracts

metadata_catalog = test_metadata_media_server_contracts.metadata_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize("category_title", [False, True])
async def test_plex_chapters_dedupe_categories_and_keep_nonnegative_offsets(
    metadata_catalog, category_title
):
    service, database, directory, _, _ = metadata_catalog
    output = directory / "plex.txt"

    def write():
        with database.sync_session_factory() as db:
            stream = db.get(Stream, 1)
            events = [
                StreamEvent(
                    stream_id=1,
                    event_type="channel.update",
                    title="Before",
                    category_name="First",
                    timestamp=stream.started_at - timedelta(minutes=1),
                ),
                StreamEvent(
                    stream_id=1,
                    event_type="channel.update",
                    title="Same category",
                    category_name="First",
                    timestamp=stream.started_at + timedelta(seconds=90),
                ),
                StreamEvent(
                    stream_id=1,
                    event_type="channel.update",
                    title=None,
                    category_name="Second",
                    timestamp=stream.started_at + timedelta(seconds=180),
                ),
            ]
            db.add_all(events)
            db.commit()
            projected = service._get_chapters_for_ffmpeg(db, stream)
            assert [item["start_time"] for item in projected] == [0, 90, 180]
            assert [item["title"] for item in projected] == ["First", "First", "Second"]
            return service._create_plex_chapters_file(
                stream, events, str(output), category_title
            )

    assert await run_in_thread_pool(write)
    text = output.read_text()
    assert "CHAPTER01=00:00:00.000" in text
    assert text.count("NAME=") == (2 if category_title else 3)
    if category_title:
        assert "CHAPTER02NAME=Second" in text and "Same category" not in text
    else:
        assert "CHAPTER02NAME=Same category" in text
        assert "CHAPTER03NAME=Chapter 3" in text
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("started", [True, False])
async def test_plex_chapter_empty_event_fallback_is_bounded(metadata_catalog, started):
    service, _, directory, _, _ = metadata_catalog
    output = directory / "empty.txt"
    stream = Stream(
        id=777,
        streamer_id=1,
        title="Whole stream",
        started_at=datetime(2026, 11, 1) if started else None,
    )
    assert await run_in_thread_pool(
        service._create_plex_chapters_file, stream, [], str(output)
    )
    assert output.read_text() == (
        "CHAPTER01=00:00:00.000\nCHAPTER01NAME=Whole stream\n" if started else ""
    )


@pytest.mark.asyncio
async def test_chapter_failed_open_returns_false_and_preserves_original(
    metadata_catalog, monkeypatch
):
    import builtins

    service, database, directory, video, _ = metadata_catalog
    output = directory / "protected.txt"
    output.write_text("existing chapter output")
    native = builtins.open

    def denied(path, *args, **kwargs):
        if Path(path) == output:
            raise PermissionError("synthetic chapter destination refusal")
        return native(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", denied)

        def write():
            with database.sync_session_factory() as db:
                return service._create_plex_chapters_file(
                    db.get(Stream, 1), [], str(output)
                )

        assert await run_in_thread_pool(write) is False
    assert output.read_text() == "existing chapter output"
    await service._create_media_server_chapters(777, str(video))
    await service._create_media_server_chapters(1, str(video))
    assert not video.with_suffix(".chapters.txt").exists()


async def test_metadata_timestamp_and_escaping_wire_formats(metadata_catalog):
    service, _, _, _, _ = metadata_catalog
    assert service._format_xml_time(3661.125) == "01:01:01.125000"
    assert service._format_xml_time(0) == "00:00:00.000000"
    assert service._escape_ffmpeg_metadata("") == "Untitled"
    assert service._escape_ffmpeg_metadata("plain") == "plain"
    assert service._escape_ffmpeg_metadata("a=b;c#d") == "a\\\\=b\\\\;c\\\\#d"
