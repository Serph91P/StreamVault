"""Metadata projections keep optional artwork/chapter failures nonfatal and pure."""

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import event, update

from app.models import Stream, StreamEvent
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_metadata_media_server_contracts

metadata_catalog = test_metadata_media_server_contracts.metadata_catalog


@pytest.mark.asyncio
async def test_missing_profile_and_stream_identity_do_not_publish_artwork(
    metadata_catalog,
):
    from app.models import StreamMetadata

    service, database, directory, _, thumbnail = metadata_catalog
    target = await run_in_thread_pool(
        service._prepare_metadata_target, 1, str(directory), "original"
    )
    assert target is not None and target.profile_url is None
    original = thumbnail.read_bytes()
    await service._prepare_artwork(target)
    await run_in_thread_pool(
        service._remember_thumbnail, None, thumbnail, existing=True
    )
    assert service.session is None and thumbnail.read_bytes() == original
    with database.sync_session_factory() as db:
        assert db.query(StreamMetadata).filter(
            StreamMetadata.stream_id == 1
        ).one().thumbnail_path == str(thumbnail)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    ["empty", "before-start", "undated", "missing-event-time", "unavailable"],
)
async def test_ffmpeg_chapter_projection_uses_closed_native_catalog(
    metadata_catalog, scenario
):
    service, database, _, _, _ = metadata_catalog

    def project():
        with database.sync_session_factory() as db:
            stream = db.get(Stream, 1)
            if scenario != "empty":
                db.add(
                    StreamEvent(
                        stream_id=1,
                        event_type="channel.update",
                        timestamp=stream.started_at - timedelta(seconds=30),
                    )
                )
                db.flush()
                if scenario == "undated":
                    stream.started_at = None
                if scenario == "missing-event-time":
                    db.execute(
                        update(StreamEvent)
                        .where(StreamEvent.stream_id == 1)
                        .values(timestamp=None)
                    )
                db.commit()
            if scenario == "unavailable":

                def unavailable(*_args):
                    raise OSError("synthetic chapter projection failure")

                event.listen(database.sync_engine, "before_cursor_execute", unavailable)
                try:
                    return service._get_chapters_for_ffmpeg(db, stream)
                finally:
                    event.remove(
                        database.sync_engine, "before_cursor_execute", unavailable
                    )
            return service._get_chapters_for_ffmpeg(db, stream)

    result = await run_in_thread_pool(project)
    assert (
        result is None
        if scenario in {"empty", "unavailable"}
        else result == [{"start_time": 0, "title": "Chapter 1"}]
    )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["json", "nfo", "media"])
async def test_metadata_stage_does_not_create_files_for_missing_stream(
    metadata_catalog, stage
):
    service, database, directory, _, _ = metadata_catalog
    before = {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    }
    target = await run_in_thread_pool(
        service._prepare_metadata_target, 1, str(directory), "absent"
    )
    assert target is not None
    assert not await run_in_thread_pool(
        service._write_metadata_stage, 999, target, stage
    )
    assert {
        path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()
    } == before
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_relative_artwork_current_directory_and_permission_fallback(
    metadata_catalog, monkeypatch
):
    service, _, directory, _, _ = metadata_catalog
    (directory / ".media" / "artwork" / "alice").mkdir(parents=True)
    assert (
        await run_in_thread_pool(
            service._relative_artwork_path, directory, "alice", "poster.jpg"
        )
        == ".media/artwork/alice/poster.jpg"
    )
    assert (
        await run_in_thread_pool(service._find_recordings_root, directory) == directory
    )

    def denied(_self):
        raise PermissionError("synthetic artwork discovery denied")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "exists", denied)
        assert (
            await run_in_thread_pool(
                service._relative_artwork_path, directory, "alice", "poster.jpg"
            )
            == ".media/artwork/alice/poster.jpg"
        )
    with monkeypatch.context() as patch:
        patch.setattr(Path, "is_dir", denied)
        assert (
            await run_in_thread_pool(service._find_recordings_root, directory) is None
        )
