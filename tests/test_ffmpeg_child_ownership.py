"""Real FFmpeg/ffprobe lifecycle ownership under repeated cancellation."""

import asyncio
import os

import pytest

from app.services.processing.ffmpeg_progress_tracker import FFmpegProgressTracker


@pytest.mark.asyncio
async def test_cancelled_ffmpeg_is_reaped_before_owner_returns(monkeypatch):
    native = asyncio.create_subprocess_exec
    children = []
    started = asyncio.Event()

    async def track(*args, **kwargs):
        process = await native(*args, **kwargs)
        children.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", track)
    task = asyncio.create_task(
        FFmpegProgressTracker().run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-re",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=64x64:rate=10",
                "-t",
                "30",
                "-f",
                "null",
                "-",
            ],
            operation="synthetic-cancel",
            total_duration_seconds=30,
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 3)
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(children) == 1
        assert children[0].returncode is not None, (
            "cancelled media owner left a child alive"
        )
    finally:
        for process in children:
            if process.returncode is None:
                process.kill()
            await process.communicate()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelled_ffprobe_is_reaped_before_owner_returns(monkeypatch, tmp_path):
    source = tmp_path / "blocked.ts"
    os.mkfifo(source)
    native = asyncio.create_subprocess_exec
    children = []
    started = asyncio.Event()

    async def track(*args, **kwargs):
        process = await native(*args, **kwargs)
        children.append(process)
        started.set()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", track)
    task = asyncio.create_task(
        FFmpegProgressTracker()._resolve_total_duration_us(None, str(source))
    )
    try:
        await asyncio.wait_for(started.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(children) == 1
        assert children[0].returncode is not None, "cancelled probe outlived its owner"
    finally:
        for process in children:
            if process.returncode is None:
                process.kill()
            await process.communicate()
        await asyncio.gather(task, return_exceptions=True)
