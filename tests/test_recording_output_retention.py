"""Bounded diagnostics must not retain completed process objects."""

import asyncio
import sys

import pytest

from app.services.recording.process_manager import ProcessManager


@pytest.mark.asyncio
async def test_released_recording_does_not_accumulate_output_state():
    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "print('done')",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    manager._remember_streamlink_output_secrets(process, [])
    await manager._collect_streamlink_output(process)
    manager._release_streamlink_output_secrets(process)
    assert not manager._streamlink_outputs
    # Released ownership does not discard diagnostics for a delayed monitor.
    stdout, _ = await manager._collect_streamlink_output(process)
    assert stdout == b"done\n"
