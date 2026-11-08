import asyncio
import sys

import pytest

from app.services.processing.ffmpeg_progress_tracker import FFmpegProgressTracker


@pytest.mark.asyncio
async def test_tracker_diagnostics_stay_bounded_and_redacted(monkeypatch):
    native = asyncio.create_subprocess_exec

    async def noisy_child(*args, **kwargs):
        return await native(
            sys.executable,
            "-c",
            "import os; [os.write(2,b'x'*1023+b'\\n') for _ in range(8192)]; os.write(2,b'https://example.invalid/live?token=synthetic-private-value\\n'); [os.write(1,b'z'*8192) for _ in range(1024)]",
            **kwargs,
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", noisy_child)
    code, stdout, stderr = await asyncio.wait_for(
        FFmpegProgressTracker().run(["ffmpeg"], operation="bounded-real-child"), 15
    )
    assert code == 0
    assert len(stdout) <= 65536
    assert len(stderr) <= 65536
    assert b"synthetic-private-value" not in stdout + stderr
