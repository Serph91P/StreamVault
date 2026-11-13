"""Chapter timing fallbacks retain nonnegative offsets and native wire units."""

from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

import pytest

from app.models import Stream, StreamEvent
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_metadata_media_server_contracts

metadata_catalog = test_metadata_media_server_contracts.metadata_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "unknown-start",
        "unknown-end",
        "pre-stream",
        "duplicate-offset",
        "single-untitled",
        "empty-events",
    ],
)
async def test_all_chapter_writers_cover_timing_and_title_fallbacks(
    metadata_catalog, case
):
    service, database, directory, _, _ = metadata_catalog

    def generate():
        start = datetime(2026, 11, 1)
        stream = Stream(
            id=1,
            streamer_id=1,
            title=None,
            started_at=None if case == "unknown-start" else start,
            ended_at=None
            if case in {"unknown-start", "unknown-end"}
            else start + timedelta(minutes=5),
        )
        offsets = (
            [-60, -30]
            if case == "pre-stream"
            else [0, 0, 90]
            if case == "duplicate-offset"
            else [0]
            if case == "single-untitled"
            else [0, 90]
        )
        events = [
            StreamEvent(
                stream_id=1,
                event_type="channel.update",
                title=None,
                category_name=None,
                timestamp=start + timedelta(seconds=offset),
            )
            for offset in offsets
        ]
        if case == "empty-events":
            events = []
        paths = {
            name: directory / f"timing.{name}" for name in ("vtt", "srt", "txt", "xml")
        }
        assert service._generate_vtt_chapters(stream, events, paths["vtt"])
        assert service._generate_srt_chapters(stream, events, paths["srt"])
        assert service._generate_ffmpeg_chapters(stream, events, paths["txt"])
        assert service._generate_xml_chapters(stream, events, paths["xml"])
        for index, event in enumerate(events):
            begin, end = service._calculate_chapter_timestamps(
                index, event, events, stream
            )
            assert 0 <= begin < end
            begin, end = service._calculate_srt_timestamps(index, event, events, stream)
            assert 0 <= begin < end
            begin, end = service._calculate_ffmpeg_timestamps(
                index, event, events, stream
            )
            assert 0 <= begin < end and end - begin >= 1000
        return {name: path.read_text() for name, path in paths.items()}

    contents = await run_in_thread_pool(generate)
    assert contents["vtt"].startswith("WEBVTT")
    assert contents["txt"].startswith(";FFMETADATA1")
    assert ET.fromstring(contents["xml"]).tag == "Chapters"
    if case == "single-untitled":
        assert "TIMEBASE=1/1" in contents["txt"] and "title=Stream" in contents["txt"]
    if case == "unknown-start":
        assert "END=86400000" in contents["txt"]
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "undated", "database"])
async def test_all_chapter_generation_fails_closed_before_files(
    metadata_catalog, monkeypatch, failure
):
    from sqlalchemy import update

    service, database, directory, video, _ = metadata_catalog
    if failure == "undated":
        with database.sync_session_factory() as db:
            db.execute(update(Stream).where(Stream.id == 1).values(started_at=None))
            db.commit()
    if failure == "database":

        def unavailable():
            raise OSError("synthetic unavailable chapter catalogue")

        monkeypatch.setattr(service, "_session_factory", unavailable)
    assert (
        await service.ensure_all_chapter_formats(
            999 if failure == "missing" else 1, str(video)
        )
        is None
    )
    assert not video.with_suffix(".vtt").exists()
    assert database.sync_engine.pool.checkedout() == 0
