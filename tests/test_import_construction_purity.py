"""Cold imports/construction must not create runtime resources."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_factory_media_mounts_keep_each_injected_storage_root(tmp_path):
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles
    from app.config.settings import get_settings
    from app.main import create_app

    roots = [tmp_path / "first", tmp_path / "second"]
    applications = []
    for root in roots:
        application = create_app(
            settings=get_settings().model_copy(
                update={"RECORDING_DIRECTORY": str(root)}
            )
        )
        applications.append(application)
        mount = next(
            route
            for route in application.routes
            if isinstance(route, Mount) and route.path == "/api/media"
        )
        assert isinstance(mount.app, StaticFiles)
        assert mount.app.directory == str(root / ".media")
        assert not root.exists()
    assert applications[0] is not applications[1]


@pytest.mark.parametrize("operation", ["lookup", "statistics"])
def test_existing_category_cache_remains_available_on_first_use(tmp_path, operation):
    from app.services.images.image_download_service import ImageDownloadService
    from app.services.images.category_image_service import CategoryImageService

    base = tmp_path / "media"
    (base / "categories").mkdir(parents=True)
    image = base / "categories" / "archived_game.jpg"
    image.write_bytes(b"previously cached image bytes")

    class CachedDownloads(ImageDownloadService):
        def get_images_base_dir(self) -> Path:
            return base

    service = CategoryImageService(CachedDownloads())
    if operation == "lookup":
        assert (
            service.get_cached_category_image("archived game")
            == "/api/media/categories/archived_game.jpg"
        )
    else:
        assert service.get_category_cache_stats()["cached_categories"] == 1
    assert image.read_bytes() == b"previously cached image bytes"


@pytest.mark.parametrize("module", ["app.models", "app.services", "app.main"])
def test_cold_import_and_construction_do_not_bootstrap_runtime_resources(
    tmp_path, module
):
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "test",
        "DATABASE_URL": "sqlite:///:memory:",
        "TWITCH_APP_ID": "synthetic",
        "TWITCH_APP_SECRET": "synthetic",
        "BASE_URL": "http://localhost:8000",
        "RECORDING_DIRECTORY": str(tmp_path / "recordings"),
        "ARTWORK_BASE_PATH": str(tmp_path / "recordings" / ".artwork"),
        "LOGS_BASE_DIR": str(tmp_path / "logs"),
        "LOG_DIR": str(tmp_path / "logs"),
        "BASE_DIR": str(tmp_path),
        "DATA_DIR": str(tmp_path / "data"),
    }
    program = """
import importlib
import os
import pathlib
import sys
import sqlalchemy
import requests
import aiohttp
import asyncio
import builtins
import secrets
import threading
import subprocess
from cryptography.fernet import Fernet

attempts = []
def forbidden(label):
    def deny(*args, **kwargs):
        attempts.append(label)
        raise AssertionError("import attempted runtime resource: " + label)
    return deny
pathlib.Path.mkdir = forbidden("mkdir")
pathlib.Path.write_text = forbidden("write_text")
pathlib.Path.write_bytes = forbidden("write_bytes")
os.mkdir = forbidden("os.mkdir")
sqlalchemy.create_engine = forbidden("engine")
requests.Session.__init__ = forbidden("requests-session")
aiohttp.ClientSession.__init__ = forbidden("aiohttp-session")
asyncio.create_task = forbidden("task")
threading.Thread.start = forbidden("thread")
subprocess.Popen = forbidden("subprocess")
Fernet.generate_key = forbidden("persistent-key-generation")
secrets.token_urlsafe = forbidden("secret-generation")
original_open = builtins.open
def read_only_open(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in "wax+"):
        return forbidden("file-write")(file)
    return original_open(file, mode, *args, **kwargs)
builtins.open = read_only_open
original_os_open = os.open
def read_only_os_open(file, flags, *args, **kwargs):
    if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
        return forbidden("os-file-write")(file)
    return original_os_open(file, flags, *args, **kwargs)
os.open = read_only_os_open
module = importlib.import_module(sys.argv[1])
if sys.argv[1] == "app.main":
    from app.config.settings import get_settings
    assert module.create_app() is module.app
    assert module.create_app(settings=get_settings()) is not module.app
assert not attempts, attempts
"""
    result = subprocess.run(
        [sys.executable, "-c", program, module],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr[-6000:]
    assert not (tmp_path / "recordings").exists()
    assert not (tmp_path / "logs").exists()
    assert not (tmp_path / "data").exists()
