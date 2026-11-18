"""Readiness must drain its real filesystem probe without swallowing cancellation."""

from __future__ import annotations

import asyncio
from pathlib import Path
import threading

import pytest


def test_recordings_path_cancellation_drains_probe_and_propagates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.routes import health

    async def exercise() -> None:
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()
        exited = threading.Event()
        directory = tmp_path / "recordings"
        directory.mkdir()
        original_is_dir = Path.is_dir

        def controlled_is_dir(path: Path) -> bool:
            if path != directory:
                return original_is_dir(path)
            loop.call_soon_threadsafe(entered.set)
            try:
                assert release.wait(5), "filesystem probe was not released"
                return original_is_dir(path)
            finally:
                exited.set()

        monkeypatch.setattr(Path, "is_dir", controlled_is_dir)
        task = asyncio.create_task(health._check_recordings_path(str(directory)))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            task.cancel("readiness-probe-cancelled")
            await asyncio.sleep(0)
            assert not task.done(), "cancellation must wait for the owned probe"
            release.set()
            with pytest.raises(asyncio.CancelledError) as cancelled:
                await task
            assert cancelled.value.args == ("readiness-probe-cancelled",)
            assert exited.is_set()
        finally:
            release.set()
            if not task.done():
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    asyncio.run(exercise())
