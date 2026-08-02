import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.routes.videos as videos
import app.services.images.category_image_service as category_images
import app.services.images.image_download_service as image_downloads
from app.services.images.category_image_service import CategoryImageService
from app.services.images.image_download_service import ImageDownloadService
from app.services.processing.recording_task_factory import RecordingTaskFactory


def _image_download_service(media_dir: Path) -> ImageDownloadService:
    service = ImageDownloadService.__new__(ImageDownloadService)
    service._initialized = True
    service.images_base_dir = media_dir
    service._failed_downloads = set()
    service.session = None
    return service


def _category_image_service(categories_dir: Path) -> CategoryImageService:
    download_service = _image_download_service(categories_dir.parent)
    service = CategoryImageService.__new__(CategoryImageService)
    service.download_service = download_service
    service.categories_dir = categories_dir
    service._category_cache = {}
    service._background_tasks = set()
    return service


class _ImageContent:
    async def iter_chunked(self, _size: int):
        yield b"image"


class _ImageResponse:
    status = 200
    headers = {"content-type": "image/jpeg"}
    content = _ImageContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _ImageSession:
    def get(self, _url: str) -> _ImageResponse:
        return _ImageResponse()


class _CategoryQuery:
    def __init__(self, category) -> None:
        self.category = category

    def filter(self, *_args):
        return self

    def first(self):
        return self.category


class _CategorySession:
    def __init__(self, category) -> None:
        self.category = category

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def query(self, *_args) -> _CategoryQuery:
        return _CategoryQuery(self.category)


async def _async_value(value):
    return value


def test_image_destination_accepts_path_inside_media_directory(tmp_path: Path) -> None:
    media_dir = tmp_path / ".media"
    media_dir.mkdir()
    destination = media_dir / "categories" / "game.jpg"
    service = _image_download_service(media_dir)

    assert service._resolve_destination_path(destination) == destination.resolve()


def test_image_destination_does_not_use_pathlib_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_dir = tmp_path / ".media"
    media_dir.mkdir()
    destination = media_dir / "categories" / "game.jpg"
    expected = Path(os.path.realpath(destination))
    service = _image_download_service(media_dir)
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda *_args, **_kwargs: pytest.fail("Path.resolve must not handle input"),
    )

    assert service._resolve_destination_path(destination) == expected


@pytest.mark.parametrize(
    "destination",
    [
        Path("../outside.jpg"),
        Path("/tmp/outside.jpg"),
    ],
)
def test_image_destination_rejects_path_outside_media_directory(
    tmp_path: Path, destination: Path
) -> None:
    media_dir = tmp_path / ".media"
    media_dir.mkdir()
    service = _image_download_service(media_dir)
    candidate = (
        media_dir / destination if not destination.is_absolute() else destination
    )

    with pytest.raises(ValueError, match="outside the media directory"):
        service._resolve_destination_path(candidate)


def test_image_destination_rejects_symlink_escape(tmp_path: Path) -> None:
    media_dir = tmp_path / ".media"
    categories_dir = media_dir / "categories"
    outside_dir = tmp_path / "outside"
    categories_dir.mkdir(parents=True)
    outside_dir.mkdir()
    (categories_dir / "escape").symlink_to(outside_dir, target_is_directory=True)
    service = _image_download_service(media_dir)

    with pytest.raises(ValueError, match="outside the media directory"):
        service._resolve_destination_path(categories_dir / "escape" / "game.jpg")


@pytest.mark.asyncio
async def test_download_rechecks_destination_before_filesystem_sinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    media_dir = tmp_path / ".media"
    media_dir.mkdir()
    outside_path = tmp_path / "outside" / "game.jpg"
    service = _image_download_service(media_dir)
    filesystem_sinks = []

    monkeypatch.setattr(
        service, "_resolve_destination_path", lambda _path: outside_path
    )
    monkeypatch.setattr(service, "get_session", lambda: _async_value(_ImageSession()))
    monkeypatch.setattr(
        Path,
        "mkdir",
        lambda path, **_kwargs: filesystem_sinks.append(("mkdir", path)),
    )
    monkeypatch.setattr(
        image_downloads.aiofiles,
        "open",
        lambda path, _mode: filesystem_sinks.append(("open", path)),
    )

    assert (
        await service.download_image("https://example.test/game.jpg", outside_path)
        is False
    )
    assert filesystem_sinks == []


def test_category_image_path_preserves_normal_filename(tmp_path: Path) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    categories_dir.mkdir(parents=True)
    service = _category_image_service(categories_dir)

    assert (
        service._category_image_path("Just Chatting")
        == (categories_dir / "just_chatting.jpg").resolve()
    )


def test_category_image_path_does_not_use_pathlib_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    categories_dir.mkdir(parents=True)
    expected = Path(os.path.realpath(categories_dir / "just_chatting.jpg"))
    service = _category_image_service(categories_dir)
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda *_args, **_kwargs: pytest.fail("Path.resolve must not handle input"),
    )

    assert service._category_image_path("Just Chatting") == expected


@pytest.mark.parametrize("category_name", ["", ".", "..", "../secret", "/tmp/secret"])
def test_category_image_path_rejects_unsafe_names(
    tmp_path: Path, category_name: str
) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    categories_dir.mkdir(parents=True)
    service = _category_image_service(categories_dir)

    with pytest.raises(ValueError, match="Invalid category name"):
        service._category_image_path(category_name)


def test_category_image_path_rejects_symlink_escape(tmp_path: Path) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    outside_file = tmp_path / "outside.jpg"
    categories_dir.mkdir(parents=True)
    outside_file.touch()
    (categories_dir / "unsafe.jpg").symlink_to(outside_file)
    service = _category_image_service(categories_dir)

    with pytest.raises(ValueError, match="outside the categories directory"):
        service._category_image_path("unsafe")


@pytest.mark.asyncio
async def test_category_download_rechecks_path_before_cached_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    categories_dir.mkdir(parents=True)
    outside_path = tmp_path / "outside.jpg"
    service = _category_image_service(categories_dir)
    filesystem_probes = []

    monkeypatch.setattr(service, "_category_image_path", lambda _name: outside_path)
    monkeypatch.setattr(
        Path,
        "exists",
        lambda path: filesystem_probes.append(path) or False,
    )

    result = await service.download_category_image(
        "Unsafe", "/api/media/categories/unsafe.jpg"
    )

    assert result is None
    assert filesystem_probes == []


def test_category_cache_lookup_rechecks_path_before_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    categories_dir = tmp_path / ".media" / "categories"
    categories_dir.mkdir(parents=True)
    outside_path = tmp_path / "outside.jpg"
    category = SimpleNamespace(box_art_url="/api/media/categories/unsafe.jpg")
    service = _category_image_service(categories_dir)
    filesystem_probes = []

    monkeypatch.setattr(service, "_category_image_path", lambda _name: outside_path)
    monkeypatch.setattr(
        category_images, "SessionLocal", lambda: _CategorySession(category)
    )
    monkeypatch.setattr(
        Path,
        "exists",
        lambda path: filesystem_probes.append(path) or False,
    )

    assert service.get_cached_category_image("Unsafe") is None
    assert filesystem_probes == []


def test_recording_path_accepts_file_inside_recording_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    recording_path = recordings_dir / "stream.ts"
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )

    assert (
        RecordingTaskFactory._validated_recording_path(str(recording_path))
        == recording_path.resolve()
    )


def test_recording_path_does_not_use_pathlib_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    recording_path = recordings_dir / "stream.ts"
    expected = Path(os.path.realpath(recording_path))
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda *_args, **_kwargs: pytest.fail("Path.resolve must not handle input"),
    )

    assert (
        RecordingTaskFactory._validated_recording_path(str(recording_path)) == expected
    )


def test_recording_path_rejects_file_outside_recording_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )

    with pytest.raises(ValueError, match="outside the recording directory"):
        RecordingTaskFactory._validated_recording_path(str(tmp_path / "outside.ts"))


def test_recording_path_rejects_symlink_escape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    outside_dir = tmp_path / "outside"
    recordings_dir.mkdir()
    outside_dir.mkdir()
    (recordings_dir / "escape").symlink_to(outside_dir, target_is_directory=True)
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )

    with pytest.raises(ValueError, match="outside the recording directory"):
        RecordingTaskFactory._validated_recording_path(
            str(recordings_dir / "escape" / "stream.ts")
        )


def test_recording_chain_uses_canonical_path_in_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    recording_path = recordings_dir / "folder" / ".." / "stream.ts"
    canonical_path = str((recordings_dir / "stream.ts").resolve())
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )

    tasks = RecordingTaskFactory.create_post_processing_chain(
        stream_id=1,
        recording_id=1,
        ts_file_path=str(recording_path),
        output_dir=str(recordings_dir),
        streamer_name="test",
        started_at="2026-01-01T00:00:00",
    )

    assert all(task.payload["ts_file_path"] == canonical_path for task in tasks)
    cleanup_task = next(task for task in tasks if task.type == "cleanup")
    assert cleanup_task.payload["files_to_remove"][0] == canonical_path


def test_recording_chain_rejects_outside_path_before_filesystem_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )
    filesystem_probes = []

    def record_is_dir(path: Path) -> bool:
        filesystem_probes.append(path)
        return False

    monkeypatch.setattr(Path, "is_dir", record_is_dir)

    with pytest.raises(ValueError, match="outside the recording directory"):
        RecordingTaskFactory.create_post_processing_chain(
            stream_id=1,
            recording_id=1,
            ts_file_path=str(tmp_path / "outside.ts"),
            output_dir=str(recordings_dir),
            streamer_name="test",
            started_at="2026-01-01T00:00:00",
        )

    assert filesystem_probes == []


def test_recording_chain_rechecks_validated_path_before_segments_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    outside_path = tmp_path / "outside.ts"
    filesystem_probes = []
    monkeypatch.setattr(
        "app.config.settings.settings.RECORDING_DIRECTORY", str(recordings_dir)
    )
    monkeypatch.setattr(
        RecordingTaskFactory,
        "_validated_recording_path",
        staticmethod(lambda _path: outside_path),
    )
    monkeypatch.setattr(
        Path,
        "is_dir",
        lambda path: filesystem_probes.append(path) or False,
    )

    with pytest.raises(ValueError, match="outside the recording directory"):
        RecordingTaskFactory.create_post_processing_chain(
            stream_id=1,
            recording_id=1,
            ts_file_path=str(outside_path),
            output_dir=str(recordings_dir),
            streamer_name="test",
            started_at="2026-01-01T00:00:00",
        )

    assert filesystem_probes == []


def test_path_check_error_message_does_not_expose_exception_text(caplog) -> None:
    secret = "sensitive filesystem detail"

    message = videos._path_check_error_message("recording path", RuntimeError(secret))

    assert message == "Unable to verify recording path"
    assert secret not in message
    assert secret in caplog.text
