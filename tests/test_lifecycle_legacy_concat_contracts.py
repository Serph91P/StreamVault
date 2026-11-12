"""Retained lifecycle concat uses native FFmpeg without provider acceptance."""

import asyncio
import os
from pathlib import Path
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned
from tests.test_recovery_concatenation_boundary import media


@pytest.mark.asyncio
async def test_legacy_lifecycle_concat_preserves_existing_manifest_and_uses_worker_io(
    image_applications, monkeypatch
):
    apps, _databases, _clients, _ = image_applications
    for app in apps:
        monkeypatch.setattr(app.state.settings, "LOGS_BASE_DIR", app.state.settings.RECORDING_DIRECTORY + "/.logs")
    directory = Path(apps[0].state.settings.RECORDING_DIRECTORY) / "segments"
    originals = await media(directory)
    manifest = directory / "concat_list_7.txt"
    manifest.write_bytes(b"existing fixture manifest must survive")
    recorder = await run_in_thread_pool(dependencies.get_application_recording_manager, HTTPConnection({"type": "http", "app": apps[0]}))
    lifecycle = recorder._service.orchestrator.lifecycle_manager
    files = [directory / name for name in sorted(originals)]
    probes = []
    native_stat = os.stat
    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(directory.parent)):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)
    try:
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            result = await lifecycle._concatenate_segments(files, 7)
        assert result is not None and result.is_file()
        assert manifest.exists() and manifest.read_bytes() == b"existing fixture manifest must survive"
        assert probes and get_ident() not in probes
        assert {path.name for path in directory.iterdir()} == set(originals) | {manifest.name}
        assert all((directory / name).read_bytes() == content for name, content in originals.items())
        child = await asyncio.create_subprocess_exec("ffmpeg", "-v", "error", "-i", str(result), "-f", "null", "-", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _output, error = await child.communicate()
        assert child.returncode == 0, error.decode()
    finally:
        await close_owned(apps)
