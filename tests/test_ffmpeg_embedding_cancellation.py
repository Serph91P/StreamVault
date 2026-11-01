"""Cancellation reaps the real remux child and its task-owned temporary file."""

import asyncio
import subprocess
import tempfile
from pathlib import Path
from threading import Event

import pytest

from app.utils.ffmpeg_utils import embed_metadata_with_ffmpeg_wrapper
from app.services.media.thumbnail_service import ThumbnailService


@pytest.mark.asyncio
@pytest.mark.parametrize("repeat_cancel", [False, True])
@pytest.mark.parametrize("operation", ["embedding", "thumbnail"])
async def test_cancelled_media_operation_drains_real_child_and_owned_files(
    tmp_path, monkeypatch, repeat_cancel, operation
):
    source = tmp_path / "source.ts"
    output = tmp_path / ("output.mp4" if operation == "embedding" else "output.jpg")
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=25",
            "-t",
            "1",
            "-threads",
            "1",
            "-c:v",
            "mpeg2video",
            str(source),
        ],
        check=True,
        capture_output=True,
    )
    original_create = asyncio.create_subprocess_exec
    original_communicate = asyncio.subprocess.Process.communicate
    started = asyncio.Event()
    release = asyncio.Event()
    children = []
    metadata_files = []
    blocked = set()
    draining = asyncio.Event()
    release_drain = asyncio.Event()
    drain_cancelled = []

    async def create(*args, **kwargs):
        process = await original_create(*args, **kwargs)
        children.append(process)
        if operation == "embedding":
            metadata_files.append(Path(args[4]))
        return process

    async def communicate(process, input=None):
        if process in children and process.pid not in blocked:
            blocked.add(process.pid)
            started.set()
            await release.wait()
        elif process in children and repeat_cancel:
            draining.set()
            try:
                await release_drain.wait()
            except asyncio.CancelledError:
                drain_cancelled.append(process.pid)
                raise
        return await original_communicate(process, input)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(asyncio.subprocess.Process, "communicate", communicate)
    coroutine = (
        embed_metadata_with_ffmpeg_wrapper(
            str(source), str(output), {"title": "cancelled"}
        )
        if operation == "embedding"
        else ThumbnailService().extract_thumbnail_from_video(
            str(source), str(output), "00:00:00"
        )
    )
    task = asyncio.create_task(coroutine)
    try:
        await asyncio.wait_for(started.wait(), 3)
        if operation == "embedding":
            assert metadata_files[0].is_file()
        task.cancel()
        if repeat_cancel:
            await asyncio.wait_for(draining.wait(), 3)
            task.cancel()
            release_drain.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert children[0].returncode is not None, (
            "cancellation must reap its real child"
        )
        assert all(not path.exists() for path in metadata_files), (
            "cancellation must remove its owned metadata"
        )
        assert not output.exists(), (
            "an interrupted output must not poison the next retry"
        )
        assert source.stat().st_size > 0
        assert not drain_cancelled, (
            "repeated shutdown cancellation must not cancel the owned drain"
        )
    finally:
        release.set()
        release_drain.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.kill()
            await original_communicate(child)
        for path in metadata_files:
            path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_cancelled_metadata_preparation_drains_worker_and_removes_its_file(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.ts"
    source.write_bytes(b"input not consumed before metadata preparation")
    output = tmp_path / "output.mp4"
    original_temporary_file = tempfile.NamedTemporaryFile
    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()
    paths = []

    def temporary_file(*args, **kwargs):
        file = original_temporary_file(*args, **kwargs)
        paths.append(Path(file.name))
        loop.call_soon_threadsafe(started.set)
        assert release.wait(3)
        return file

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", temporary_file)
    task = asyncio.create_task(
        embed_metadata_with_ffmpeg_wrapper(
            str(source), str(output), {"title": "cancelled"}
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert paths and not paths[0].exists(), (
            "drained metadata preparation must not leak its file"
        )
        assert not output.exists()
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for path in paths:
            path.unlink(missing_ok=True)
