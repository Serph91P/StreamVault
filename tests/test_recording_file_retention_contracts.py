"""Process-aware source retention with changing/unreadable output and bounded clock."""

import asyncio
import builtins

import psutil
import pytest

from app.services.recording import file_operations as module


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["growing", "small", "read-denied", "inspection-error"]
)
async def test_process_cleanup_keeps_source_until_output_is_stable_and_readable(
    tmp_path, monkeypatch, case
):
    source = tmp_path / "capture.ts"
    source.write_bytes(b"preserve source")
    output = source.with_suffix(".mp4")
    with output.open("wb") as file:
        file.truncate(100 if case == "small" else 1024 * 1024 + 1)
    clock = [0.0]
    sleeps = []
    native_open = builtins.open

    async def advance(delay):
        sleeps.append(delay)
        clock[0] += delay
        if case == "growing":
            with output.open("ab") as file:
                file.write(b"growing")

    def open_file(path, *args, **kwargs):
        if str(path) == str(output) and case == "read-denied":
            raise PermissionError("synthetic unreadable output")
        return native_open(path, *args, **kwargs)

    monkeypatch.setattr(module, "monotonic", lambda: clock[0])
    monkeypatch.setattr(asyncio, "sleep", advance)
    monkeypatch.setattr(builtins, "open", open_file)
    if case == "inspection-error":

        def unavailable(*_args):
            raise RuntimeError("synthetic process inspection unavailable")

        monkeypatch.setattr(psutil, "process_iter", unavailable)
        assert (
            await module.check_ffmpeg_processes_for_file(str(source), str(output)) == []
        )
    else:
        assert (
            await module.intelligent_ts_cleanup(str(source), max_wait_time=15) is False
        )
        assert sleeps and clock[0] == 15
    assert source.read_bytes() == b"preserve source" and output.exists()


@pytest.mark.asyncio
async def test_process_cleanup_ignores_missing_or_non_transport_source(tmp_path):
    path = tmp_path / "existing.mp4"
    path.write_bytes(b"keep")
    assert await module.intelligent_ts_cleanup(str(path), max_wait_time=0) is None
    assert (
        await module.intelligent_ts_cleanup(
            str(tmp_path / "missing.ts"), max_wait_time=0
        )
        is None
    )
    assert path.read_bytes() == b"keep"
