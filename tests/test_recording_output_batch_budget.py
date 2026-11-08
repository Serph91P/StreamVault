"""Performance contract: drain batches, not a sanitizer call per log line."""

import asyncio
import cProfile
import sys

import pytest

from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_auth_policy import is_twitch_auth_rejection
from app.utils.security import StreamingStreamlinkOutputSanitizer


def test_no_known_secrets_does_not_build_per_character_prefix_search_lists():
    sanitizer = StreamingStreamlinkOutputSanitizer(())
    sanitizer.feed(
        b"warmup\n"
    )  # Compile shared redaction regexes outside the allocation profile.
    profiler = cProfile.Profile()
    profiler.enable()
    safe = sanitizer.feed(b"ordinary diagnostic\n" * 4096)
    profiler.disable()
    list_appends = sum(
        entry.callcount
        for entry in profiler.getstats()
        if isinstance(entry.code, str) and "'append' of 'list'" in entry.code
    )
    assert list_appends < 100, (
        f"empty secret-prefix search allocated {list_appends} list entries"
    )
    assert safe == "ordinary diagnostic\n" * 4096


@pytest.mark.asyncio
async def test_dense_newlines_are_sanitized_in_bounded_batches():
    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import os; [os.write(2,b'x'*63+b'\\n') for _ in range(16384)]",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    profiler = cProfile.Profile()
    profiler.enable()
    manager._remember_streamlink_output_secrets(process, [])
    try:
        _, stderr = await manager._collect_streamlink_output(process)
    finally:
        profiler.disable()
        if process.returncode is None:
            process.kill()
            await manager._collect_streamlink_output(process)
        manager._release_streamlink_output_secrets(process)
    feed = StreamingStreamlinkOutputSanitizer.feed.__code__
    calls = sum(entry.callcount for entry in profiler.getstats() if entry.code is feed)
    assert calls < 1024, (
        f"one expensive redaction per short line: {calls} calls per MiB"
    )
    auth_calls = sum(
        entry.callcount
        for entry in profiler.getstats()
        if entry.code is is_twitch_auth_rejection.__code__
    )
    assert auth_calls == 0, "ordinary output cannot contain a token/401 rejection"
    assert stderr == (b"x" * 63 + b"\n") * 1024
