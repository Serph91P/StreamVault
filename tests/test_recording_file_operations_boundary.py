"""Process-aware cleanup probes use exact files and never block the owner loop."""

import asyncio
import os
import subprocess
from threading import get_ident

import psutil
import pytest

from app.services.recording.file_operations import (
    check_ffmpeg_processes_for_file,
    find_existing_mp4,
)
from app.services.processing.post_processing_task_handlers import (
    PostProcessingTaskHandlers,
)


@pytest.mark.asyncio
async def test_ffmpeg_inspection_is_off_loop_and_does_not_claim_peer_basename(
    tmp_path, monkeypatch
):
    children = []
    paths = []
    inspected = []
    native_process_iter = psutil.process_iter
    loop_thread = get_ident()

    def process_iter(*args, **kwargs):
        inspected.append(get_ident())
        return native_process_iter(*args, **kwargs)

    try:
        for name in ("first", "second"):
            directory = tmp_path / name
            directory.mkdir()
            path = directory / "capture.ts"
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=320x180:rate=5",
                    "-t",
                    "1",
                    "-threads",
                    "1",
                    "-c:v",
                    "mpeg2video",
                    str(path),
                ],
                check=True,
                capture_output=True,
            )
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-progress",
                "pipe:1",
                "-re",
                "-stream_loop",
                "-1",
                "-i",
                str(path),
                "-f",
                "null",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            children.append(process)
            paths.append(path)

            async def ready():
                while True:
                    line = await process.stdout.readline()
                    assert line, (
                        "real FFmpeg exited before its first progress acknowledgement"
                    )
                    if line.startswith(b"progress="):
                        return

            await asyncio.wait_for(ready(), 3)
        with monkeypatch.context() as watched:
            watched.setattr(psutil, "process_iter", process_iter)
            for index, path in enumerate(paths):
                owners = await check_ffmpeg_processes_for_file(
                    str(path), str(path.with_suffix(".mp4"))
                )
                assert {owner["pid"] for owner in owners} == {children[index].pid}
        assert inspected and loop_thread not in inspected
    finally:
        for process in children:
            if process.returncode is None:
                process.kill()
            await process.communicate()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["stable", "missing_output", "small_output", "deadline"]
)
async def test_intelligent_cleanup_forwards_outcome_and_keeps_file_io_off_loop(
    tmp_path, monkeypatch, case
):
    source = tmp_path / "capture.ts"
    source.write_bytes(b"source")
    output = source.with_suffix(".mp4")
    if case != "missing_output":
        with output.open("wb") as file:
            file.truncate(100 if case == "small_output" else 1024 * 1024 + 1)
    handler = PostProcessingTaskHandlers()
    accesses = []
    native_stat = os.stat
    loop_thread = get_ident()

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            accesses.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        with monkeypatch.context() as watched:
            watched.setattr(os, "stat", stat)
            result = await handler._intelligent_ts_cleanup(
                str(source), str(output), 30 if case == "stable" else 0
            )
        assert result is (case == "stable")
        assert source.exists() is (case != "stable")
        if case != "deadline":
            assert accesses and loop_thread not in accesses
    finally:
        await handler.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["fallback-remove", "fallback-missing"])
async def test_intelligent_cleanup_falls_back_to_simple_removal_off_loop(
    tmp_path, monkeypatch, case
):
    """Native intelligent-cleanup failure degrades to simple removal, not false success.

    Value: protects=the TS source is still reclaimed (or reported unreclaimed) when the
    process-aware cleanup path itself raises;
    fails_when=the fallback swallows the fault without removing the file, or reports
    removal of a file that no longer exists;
    why_new=the existing table covers timeout/deadline outcomes, not a raising helper;
    seam=none; no_claim=real FFmpeg process attachment or provider capture.
    """
    import app.services.recording.file_operations as file_operations

    source = tmp_path / "capture.ts"
    if case == "fallback-remove":
        source.write_bytes(b"source")
    handler = PostProcessingTaskHandlers()
    accesses = []
    native_stat = os.stat
    loop_thread = get_ident()

    async def raising_cleanup(*_args, **_kwargs):
        raise RuntimeError("synthetic intelligent-cleanup failure")

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            accesses.append(get_ident())
        return native_stat(path, *args, **kwargs)

    try:
        with monkeypatch.context() as watched:
            watched.setattr(file_operations, "intelligent_ts_cleanup", raising_cleanup)
            watched.setattr(os, "stat", stat)
            result = await handler._intelligent_ts_cleanup(
                str(source), str(tmp_path / "output.mp4"), 30
            )
        assert result is (True if case == "fallback-remove" else None)
        assert source.exists() is False
        if case == "fallback-remove":
            assert accesses and loop_thread not in accesses
    finally:
        await handler.cleanup()


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["preferred", "largest", "none"])
async def test_existing_mp4_selection_is_an_off_loop_scalar(
    tmp_path, monkeypatch, case
):
    preferred = tmp_path / "preferred.mp4"
    largest = tmp_path / "largest.mp4"
    if case != "none":
        with preferred.open("wb") as file:
            file.truncate(1000001 if case == "preferred" else 100)
        with largest.open("wb") as file:
            file.truncate(2000000)
    accesses = []
    loop_thread = get_ident()
    native_stat = os.stat

    def stat(path, *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            accesses.append(get_ident())
        return native_stat(path, *args, **kwargs)

    with monkeypatch.context() as watched:
        watched.setattr(os, "stat", stat)
        result = await find_existing_mp4(str(tmp_path), str(preferred))
    assert result == (
        str(preferred)
        if case == "preferred"
        else str(largest)
        if case == "largest"
        else None
    )
    assert accesses and loop_thread not in accesses
