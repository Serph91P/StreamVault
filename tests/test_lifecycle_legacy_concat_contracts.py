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
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    directory = Path(apps[0].state.settings.RECORDING_DIRECTORY) / "segments"
    originals = await media(directory)
    manifest = directory / "concat_list_7.txt"
    manifest.write_bytes(b"existing fixture manifest must survive")
    recorder = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0]}),
    )
    lifecycle = recorder._service.orchestrator.lifecycle_manager
    files = [directory / name for name in sorted(originals)]
    probes = []
    native_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(
            str(directory.parent)
        ):
            probes.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            result = await lifecycle._concatenate_segments(files, 7)
        assert result is not None and result.is_file()
        assert (
            manifest.exists()
            and manifest.read_bytes() == b"existing fixture manifest must survive"
        )
        assert probes and get_ident() not in probes
        assert {path.name for path in directory.iterdir()} == set(originals) | {
            manifest.name
        }
        assert all(
            (directory / name).read_bytes() == content
            for name, content in originals.items()
        )
        child = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(result),
            "-f",
            "null",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _output, error = await child.communicate()
        assert child.returncode == 0, error.decode()
    finally:
        await close_owned(apps)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "directory",
        "invalid-id",
        "non-ts",
        "unsafe",
        "bad-media",
        "empty",
        "skip-invalid",
    ],
)
async def test_legacy_concat_rejects_invalid_inputs_and_keeps_sources(
    image_applications, monkeypatch, case
):
    apps, _databases, _clients, _ = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    root = Path(apps[0].state.settings.RECORDING_DIRECTORY)
    directory = root / ("unsafe;output" if case == "unsafe" else "safe") / "segments"
    directory.parent.mkdir()
    if case == "skip-invalid":
        originals = await media(directory)
    else:
        directory.mkdir()
        (directory / "segment_000.ts").write_bytes(
            b"not decodable, negative-path media"
        )
        originals = {"segment_000.ts": (directory / "segment_000.ts").read_bytes()}
    files = [directory / name for name in sorted(originals)]
    identity = 0 if case == "invalid-id" else 7
    if case == "missing":
        files = [directory / "missing.ts"]
    elif case == "directory":
        files = [directory]
    elif case == "non-ts":
        other = directory / "not-a-transport.log"
        other.write_text("not a TS source")
        files = [other]
    elif case == "empty":
        files = []
    elif case == "skip-invalid":
        other = directory / "not-a-transport.log"
        other.write_text("not a TS source")
        files += [directory / "missing.ts", other]
    recorder = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0]}),
    )
    lifecycle = recorder._service.orchestrator.lifecycle_manager
    try:
        result = await lifecycle._concatenate_segments(files, identity)
        if case == "skip-invalid":
            assert result is not None and result.stat().st_size > 0
        else:
            assert result is None
        assert all(
            (directory / name).read_bytes() == content
            for name, content in originals.items()
        )
        assert not list(directory.glob("concat_list_*.txt"))
    finally:
        await close_owned(apps)


@pytest.mark.asyncio
async def test_legacy_concat_cancel_during_real_manifest_preparation_drains_and_removes_only_own_file(
    image_applications, monkeypatch
):
    import tempfile
    from threading import Event

    apps, _databases, _clients, _ = image_applications
    for app in apps:
        monkeypatch.setattr(
            app.state.settings,
            "LOGS_BASE_DIR",
            app.state.settings.RECORDING_DIRECTORY + "/.logs",
        )
    directory = Path(apps[0].state.settings.RECORDING_DIRECTORY) / "segments"
    originals = await media(directory)
    existing = directory / "concat_list_7.txt"
    existing.write_bytes(b"keep original manifest")
    recorder = await run_in_thread_pool(
        dependencies.get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0]}),
    )
    lifecycle = recorder._service.orchestrator.lifecycle_manager
    native_temporary = tempfile.NamedTemporaryFile
    entered, release = Event(), Event()
    created = []

    def temporary(*args, **kwargs):
        value = native_temporary(*args, **kwargs)
        if kwargs.get("dir") is not None and Path(kwargs["dir"]) == directory:
            created.append(Path(value.name))
            entered.set()
            assert release.wait(5)
        return value

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", temporary)
    task = asyncio.create_task(
        lifecycle._concatenate_segments(
            [directory / name for name in sorted(originals)], 7
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert created and all(not path.exists() for path in created)
        assert existing.read_bytes() == b"keep original manifest"
        assert all(
            (directory / name).read_bytes() == content
            for name, content in originals.items()
        )
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await close_owned(apps)
