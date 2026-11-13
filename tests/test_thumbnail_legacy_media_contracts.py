"""Retained legacy media entrypoints: actual MP4/JPEG, DB and Plex copies.

These explicit legacy adapters use only their rebound fixture defaults. They do
not establish app-owned/closed-session guarantees of create_unified_thumbnail.
"""

import importlib
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app import dependencies
from app.models import Stream, StreamMetadata
from tests.test_image_http_boundary import image_origin as image_origin
from app.services.media.thumbnail_service import ThumbnailService
from app.services.system.logging_service import LoggingService
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.fixture
async def legacy_thumbnail_catalogue(image_applications, tmp_path, monkeypatch):
    _, databases, _, _ = image_applications
    database = databases[0]
    module = importlib.import_module("app.services.media.thumbnail_service")
    monkeypatch.setattr(module, "SessionLocal", database.sync_session_factory)
    logs = LoggingService(str(tmp_path / "legacy-logs"), isolated=True)
    monkeypatch.setattr(
        importlib.import_module("app.services.system.logging_service"),
        "logging_service",
        logs,
    )
    root = tmp_path / "legacy-media"
    root.mkdir()
    video = root / "fixture.mp4"
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=1:duration=700",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-y",
            str(video),
        ],
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    with database.sync_session_factory() as session:
        session.add(Stream(id=70, streamer_id=1, recording_path=str(video)))
        session.flush()
        session.add(
            StreamMetadata(stream_id=70, json_path=str(root / "fixture.info.json"))
        )
        session.commit()
    # A cached invalid image selects real video fallback without provider access.
    (root / "fixture-thumb.jpg").write_bytes(b"tiny")
    try:
        yield (
            ThumbnailService(session_factory=database.sync_session_factory),
            database,
            root,
            video,
        )
    finally:
        logs.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "ensure_thumbnail",
        "ensure_thumbnail_with_fallback",
        "generate_thumbnail_from_mp4",
    ],
)
async def test_legacy_video_entrypoints_publish_real_frames_and_plex_copies(
    legacy_thumbnail_catalogue, method
):
    service, database, root, video = legacy_thumbnail_catalogue
    if method == "generate_thumbnail_from_mp4":
        result = await service.generate_thumbnail_from_mp4(70, str(video))
    else:
        result = await getattr(service, method)(70, str(root))
    assert result is not None
    result = Path(result)
    assert result.is_file() and result.stat().st_size > 1000
    with Image.open(result) as image:
        assert image.format == "JPEG" and image.size == (320, 180)
    with database.sync_session_factory() as session:
        assert session.get(StreamMetadata, 1).thumbnail_path == str(result)
    assert (root / "fixture-thumb.jpg").read_bytes() == result.read_bytes()
    assert (root / "poster.jpg").read_bytes() == result.read_bytes()
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method",
    [
        "download_thumbnail",
        "ensure_thumbnail",
        "ensure_thumbnail_with_fallback",
        "generate_thumbnail_from_mp4",
    ],
)
async def test_legacy_missing_stream_does_not_publish_file_or_metadata(
    legacy_thumbnail_catalogue, method
):
    service, database, root, video = legacy_thumbnail_catalogue
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    result = await getattr(service, method)(
        999, str(video) if method == "generate_thumbnail_from_mp4" else str(root)
    )
    assert result is None
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before
    with database.sync_session_factory() as session:
        assert session.query(StreamMetadata).count() == 1
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_cached_legacy_thumbnail_is_returned_without_rewriting(
    legacy_thumbnail_catalogue,
):
    service, database, root, _ = legacy_thumbnail_catalogue
    path = root / "fixture-thumb.jpg"
    Image.new("RGB", (320, 180), "blue").save(path)
    before = path.read_bytes()
    assert await service.download_thumbnail(70, str(root)) == str(path)
    assert path.read_bytes() == before
    with database.sync_session_factory() as session:
        assert session.get(StreamMetadata, 1).thumbnail_path is None
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("layout", ["recording", "fallback", "missing-metadata"])
async def test_legacy_http_download_writes_actual_image_and_persists_source(
    legacy_thumbnail_catalogue, image_applications, image_origin, monkeypatch, layout
):
    service, database, root, _ = legacy_thumbnail_catalogue
    apps, _, _, _ = image_applications
    base, seen = image_origin
    images = dependencies._get_application_image_service(apps[0])
    monkeypatch.setattr(
        importlib.import_module("app.services.unified_image_service"),
        "unified_image_service",
        images,
    )

    async def source(*_args):
        return base + "/thumbnail"

    monkeypatch.setattr(service, "get_stream_thumbnail", source)
    (root / "fixture-thumb.jpg").unlink()
    with database.sync_session_factory() as session:
        if layout == "fallback":
            session.get(Stream, 70).recording_path = None
        elif layout == "missing-metadata":
            session.query(StreamMetadata).delete()
        session.commit()
    result = await service.download_thumbnail(70, str(root))
    assert result is not None
    with Image.open(result) as image:
        assert image.format == "PNG" and image.size == (128, 128)
    with database.sync_session_factory() as session:
        row = session.query(StreamMetadata).filter_by(stream_id=70).one()
        assert (
            row.thumbnail_path == str(result)
            and row.thumbnail_url == base + "/thumbnail"
        )
    if layout == "fallback":
        assert (root / "fixture-thumb.jpg").read_bytes() == Path(result).read_bytes()
        assert (root / "poster.jpg").read_bytes() == Path(result).read_bytes()
    assert [path for path, *_ in seen] == ["/thumbnail"]
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_legacy_http_rejection_preserves_catalogue_and_output(
    legacy_thumbnail_catalogue, image_applications, image_origin, monkeypatch
):
    service, database, root, _ = legacy_thumbnail_catalogue
    apps, _, _, _ = image_applications
    base, seen = image_origin
    images = dependencies._get_application_image_service(apps[0])
    monkeypatch.setattr(
        importlib.import_module("app.services.unified_image_service"),
        "unified_image_service",
        images,
    )

    async def source(*_args):
        return base + "/denied"

    monkeypatch.setattr(service, "get_stream_thumbnail", source)
    (root / "fixture-thumb.jpg").unlink()
    assert await service.download_thumbnail(70, str(root)) is None
    assert not (root / "fixture-thumb.jpg").exists()
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).filter_by(stream_id=70).one().thumbnail_path
            is None
        )
    assert [path for path, *_ in seen] == ["/denied"]
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_legacy_placeholder_heuristic_and_invalid_image_are_nonfatal():
    import io

    service = ThumbnailService()
    image = Image.new("L", (128, 128), 100)
    output = io.BytesIO()
    image.save(output, format="PNG")
    assert await service._is_placeholder_image(output.getvalue()) is True
    assert await service._is_placeholder_image(b"not-a-decodable-image") is False
    url = await service.get_stream_thumbnail("fixture", width=320, height=180)
    assert url.startswith(
        "https://static-cdn.jtvnw.net/previews-ttv/live_user_fixture-320x180.jpg?t="
    )
    assert url.rsplit("=", 1)[1].isdigit()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method", ["ensure_thumbnail", "ensure_thumbnail_with_fallback"]
)
@pytest.mark.parametrize("copy_denied", [False, True])
async def test_legacy_stored_thumbnail_fallback_preserves_image_and_optional_copy_errors(
    legacy_thumbnail_catalogue, monkeypatch, caplog, method, copy_denied
):
    import shutil

    service, database, root, _ = legacy_thumbnail_catalogue
    stored = root / "stored.jpg"
    Image.new("RGB", (320, 180), "blue").save(stored)
    original = stored.read_bytes()
    folder = root / "without-mp4"
    folder.mkdir()
    with database.sync_session_factory() as session:
        row = session.query(StreamMetadata).filter_by(stream_id=70).one()
        row.thumbnail_path, row.json_path = (
            str(stored),
            str(folder / "fixture.info.json"),
        )
        session.commit()
    if copy_denied:
        native_copy = shutil.copy2

        def reject_copy(source, destination, *args, **kwargs):
            if str(source) == str(stored) and Path(destination).parent == folder:
                raise PermissionError("synthetic-optional-thumbnail-copy-denied")
            return native_copy(source, destination, *args, **kwargs)

        monkeypatch.setattr(shutil, "copy2", reject_copy)
    for _ in range(2):
        assert await getattr(service, method)(70, str(root)) == str(stored)
        assert stored.read_bytes() == original
    if copy_denied:
        assert "synthetic-optional-thumbnail-copy-denied" in caplog.text
        assert not (folder / "fixture-thumb.jpg").exists()
    else:
        assert (folder / "fixture-thumb.jpg").read_bytes() == original
        assert (folder / "poster.jpg").read_bytes() == original
    with database.sync_session_factory() as session:
        assert session.query(StreamMetadata).filter_by(
            stream_id=70
        ).one().thumbnail_path == str(stored)
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cached", [True, False])
async def test_legacy_missing_mp4_attempts_real_media_fallback_without_false_catalogue_write(
    legacy_thumbnail_catalogue, image_applications, image_origin, monkeypatch, cached
):
    service, database, root, _ = legacy_thumbnail_catalogue
    apps, _, _, _ = image_applications
    base, seen = image_origin
    path = root / "fixture-thumb.jpg"
    if cached:
        Image.new("RGB", (320, 180), "blue").save(path)
        original = path.read_bytes()
    else:
        path.unlink()
        images = dependencies._get_application_image_service(apps[0])
        monkeypatch.setattr(
            importlib.import_module("app.services.unified_image_service"),
            "unified_image_service",
            images,
        )

        async def source(*_args):
            return base + "/denied"

        monkeypatch.setattr(service, "get_stream_thumbnail", source)
    result = await service.generate_thumbnail_from_mp4(70, str(root / "absent.mp4"))
    if cached:
        assert Path(result) == path and path.read_bytes() == original
        assert seen == []
    else:
        assert result is None and not path.exists()
        assert [request_path for request_path, *_ in seen] == ["/denied"]
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).filter_by(stream_id=70).one().thumbnail_path
            is None
        )
    assert database.sync_engine.pool.checkedout() == 0


@pytest.mark.asyncio
async def test_legacy_mp4_generation_creates_missing_metadata_after_real_frame(
    legacy_thumbnail_catalogue,
):
    service, database, root, video = legacy_thumbnail_catalogue
    with database.sync_session_factory() as session:
        session.query(StreamMetadata).delete()
        session.commit()
    result = await service.generate_thumbnail_from_mp4(70, str(video))
    assert result is not None and Path(result).stat().st_size > 1000
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).filter_by(stream_id=70).one().thumbnail_path
            == result
        )
    assert (root / "poster.jpg").read_bytes() == Path(result).read_bytes()


@pytest.mark.asyncio
async def test_unified_thumbnail_db_failure_is_not_reported_as_published(
    legacy_thumbnail_catalogue,
):
    from sqlalchemy import event

    service, database, root, video = legacy_thumbnail_catalogue

    def reject_update(_conn, _cursor, sql, *_):
        if sql.lstrip().upper().startswith("UPDATE STREAM_METADATA"):
            raise RuntimeError("synthetic-thumbnail-publication-fault")

    event.listen(database.sync_engine, "before_cursor_execute", reject_update)
    try:
        assert await service.create_unified_thumbnail(70, str(video)) is None
    finally:
        event.remove(database.sync_engine, "before_cursor_execute", reject_update)
    assert (root / "fixture-thumb.jpg").stat().st_size > 1000
    with database.sync_session_factory() as session:
        assert (
            session.query(StreamMetadata).filter_by(stream_id=70).one().thumbnail_path
            is None
        )
    assert database.sync_engine.pool.checkedout() == 0
