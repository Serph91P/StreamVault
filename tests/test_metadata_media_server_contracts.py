"""Native media-server sidecars, link fallbacks and manual chapter contracts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.database import Base, DatabaseLifecycle
from app.models import RecordingSettings, Stream, Streamer, StreamEvent, StreamMetadata
from app.services.media.metadata_service import MetadataService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.fixture
async def metadata_catalog(tmp_path):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'catalog.db'}")
    root = tmp_path / "recordings"
    directory = root / "alice" / "Season 2026-11"
    directory.mkdir(parents=True)
    video = directory / "original.mp4"
    video.write_bytes(b"synthetic sidecar target, not a decoding fixture")
    video.with_suffix(".nfo").write_text(
        "<episodedetails><title>original</title></episodedetails>"
    )
    thumb = directory / "source.jpg"
    thumb.write_bytes(b"synthetic artwork copy bytes")
    service = MetadataService(
        session_factory=database.sync_session_factory,
        recordings_root_provider=lambda: root,
    )
    try:
        with database.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as db:
            db.add(Streamer(id=1, username="alice", twitch_id="alice"))
            db.flush()
            started = datetime(2026, 11, 1, tzinfo=timezone.utc)
            db.add(
                Stream(
                    id=1,
                    streamer_id=1,
                    title="Changed title",
                    episode_number=2,
                    started_at=started,
                    ended_at=started + timedelta(hours=1),
                    recording_path=str(video),
                )
            )
            db.flush()
            db.add(StreamMetadata(stream_id=1, thumbnail_path=str(thumb)))
            db.add(RecordingSettings(id=1, filename_preset="plex"))
            db.commit()
        yield service, database, directory, video, thumb
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "links",
    [
        "symlink",
        "copy-fallback",
        "existing",
        "same-name",
        "hardlink-branch",
        "hardlink-fallback",
        "no-stored-path",
        "no-episode",
    ],
)
async def test_plex_sidecars_preserve_exact_source_and_retry(
    metadata_catalog, monkeypatch, links
):
    import app.services.media.metadata_service as module

    service, database, directory, video, thumb = metadata_catalog

    def create():
        with database.sync_session_factory() as db:
            stream = db.get(Stream, 1)
            if links == "same-name":
                renamed = directory / "alice - S202611E02 - Changed title.mp4"
                video.rename(renamed)
                video.with_suffix(".nfo").rename(renamed.with_suffix(".nfo"))
                stream.recording_path = str(renamed)
                db.commit()
            if links == "no-stored-path":
                stream.recording_path = None
            if links == "no-episode":
                stream.episode_number = None
            return service._create_media_server_specific_files(
                stream, directory, str(thumb), db, streamer=db.get(Streamer, 1)
            )

    if links == "copy-fallback":

        def refused(*_args, **_kwargs):
            raise PermissionError("synthetic filesystem has no symlink support")

        monkeypatch.setattr(module.os, "symlink", refused)
    if links.startswith("hardlink"):
        # Native Linux hardlinks exercise the existing platform branch, not a
        # Windows filesystem or physical-player acceptance claim.
        import os
        from types import SimpleNamespace

        def hardlink(source, destination):
            if links == "hardlink-fallback":
                raise PermissionError("synthetic hardlink denial")
            os.link(source, destination)

        monkeypatch.setattr(
            module, "os", SimpleNamespace(name="nt", path=os.path, link=hardlink)
        )
    if links == "existing":
        assert await run_in_thread_pool(create)
    assert await run_in_thread_pool(create)
    expected = (
        directory
        / f"alice - S202611E{'01' if links == 'no-episode' else '02'} - Changed title.mp4"
    )
    assert expected.read_bytes() == b"synthetic sidecar target, not a decoding fixture"
    assert "<episodedetails>" in expected.with_suffix(".nfo").read_text()
    assert expected.is_symlink() is (
        links in {"symlink", "existing", "no-stored-path", "no-episode"}
    )
    for name in [
        "poster.jpg",
        "original-thumb.jpg"
        if links != "same-name"
        else "alice - S202611E02 - Changed title-thumb.jpg",
        "original.tbn"
        if links != "same-name"
        else "alice - S202611E02 - Changed title.tbn",
        "season-poster.jpg",
    ]:
        assert (directory / name).read_bytes() == thumb.read_bytes()
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_plex_never_links_into_another_streamer_folder(metadata_catalog):
    service, database, directory, video, thumb = metadata_catalog
    peer = directory.parent.parent / "bob"
    peer.mkdir()
    peer_video = peer / "peer.mp4"
    peer_video.write_bytes(b"peer")

    def create():
        with database.sync_session_factory() as db:
            stream = db.get(Stream, 1)
            stream.recording_path = str(peer_video)
            return service._create_media_server_specific_files(
                stream, peer, str(thumb), db, streamer=db.get(Streamer, 1)
            )

    assert await run_in_thread_pool(create)
    assert not any(path.is_symlink() for path in peer.iterdir())
    assert peer_video.read_bytes() == b"peer"
    assert video.exists()


@pytest.mark.asyncio
async def test_manual_chapters_replace_only_owner_events_and_generate_real_formats(
    metadata_catalog,
):
    service, database, directory, video, _ = metadata_catalog
    text = directory / "manual.txt"
    text.write_text("ignored line\n0:00:00 Opening\n0:01:30 Main\n0:59:00 Ending\n")
    original = text.read_bytes()
    result = await service.import_manual_chapters(1, str(text), str(video))
    assert result and len(result) == 4
    assert all(Path(path).is_file() for path in result.values())
    assert "Opening" in video.with_suffix(".vtt").read_text()
    assert "Main" in video.with_suffix(".srt").read_text()
    with database.sync_session_factory() as db:
        rows = (
            db.query(StreamEvent)
            .filter(StreamEvent.stream_id == 1)
            .order_by(StreamEvent.timestamp)
            .all()
        )
        assert [row.title for row in rows] == ["Opening", "Main", "Ending"]
        assert all(row.event_type == "manual.chapter" for row in rows)
    await service._create_media_server_chapters(1, str(video))
    assert "CHAPTER02=00:01:30.000" in video.with_suffix(".chapters.txt").read_text()
    assert text.read_bytes() == original
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state", ["missing-file", "no-chapters", "missing-stream", "read-error"]
)
async def test_manual_chapter_invalid_input_preserves_prior_events(
    metadata_catalog, monkeypatch, state
):
    import builtins

    service, database, directory, video, _ = metadata_catalog
    text = directory / "manual.txt"
    if state != "missing-file":
        text.write_text("invalid" if state == "no-chapters" else "0:00:00 New")
    with database.sync_session_factory() as db:
        db.add(
            StreamEvent(
                stream_id=1,
                event_type="channel.update",
                title="Preserved",
                timestamp=datetime(2026, 11, 1, tzinfo=timezone.utc),
            )
        )
        db.commit()
    if state == "read-error":
        native = builtins.open

        def denied(path, *args, **kwargs):
            if Path(path) == text:
                raise PermissionError("synthetic chapter read denial")
            return native(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", denied)
    assert (
        await service.import_manual_chapters(
            999 if state == "missing-stream" else 1, str(text), str(video)
        )
        is None
    )
    with database.sync_session_factory() as db:
        assert [row.title for row in db.query(StreamEvent).all()] == ["Preserved"]
    assert not video.with_suffix(".vtt").exists()
    assert database.sync_engine.pool.checkedout() == 0
