"""Chunking, overlength and cancellation of real recording diagnostics."""

import asyncio
import sys

import pytest

from app.services.recording.process_manager import ProcessManager


@pytest.mark.asyncio
async def test_recording_tail_redacts_chunk_split_values_and_retains_early_failure():
    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    secret = "synthetic-token-crossing-chunks"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import os,time; "
        "os.write(2,b'Authorization token invalid\\nProxyError\\n'); "
        "os.write(2,b'k'*8185+b'synthetic-token-'); time.sleep(.02); "
        "os.write(2,b'crossing-chunks https://proxy.invalid/signed?secret=private\\n'); "
        "[os.write(2,b'ordinary diagnostic\\n'*1024) for _ in range(100)]; "
        "os.write(2,b'url-without-newline'+b'z'*200000)",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    manager._remember_streamlink_output_secrets(process, [f"--token={secret}"])
    try:
        _, stderr = await manager._collect_streamlink_output(process)
        assert len(stderr) <= 65536
        assert b"Authorization token invalid" in stderr
        assert b"ProxyError" in stderr
        assert b"[overlong diagnostic line omitted]" in stderr
        for forbidden in (
            secret.encode(),
            b"crossing-chunks",
            b"signed",
            b"private",
            b"z" * 100,
        ):
            assert forbidden not in stderr
    finally:
        if process.returncode is None:
            process.kill()
        await manager._collect_streamlink_output(process)
        manager._release_streamlink_output_secrets(process)


@pytest.mark.asyncio
async def test_cancelled_output_consumer_does_not_cancel_the_only_pipe_owner(tmp_path):
    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    marker = tmp_path / "finished.ts"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import os,time,pathlib,sys; time.sleep(.1); "
        "[os.write(2,b'continuous output\\n'*1024) for _ in range(100)]; "
        "pathlib.Path(sys.argv[1]).write_bytes(b'finished')",
        str(marker),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    manager._remember_streamlink_output_secrets(process, [])
    consumer = asyncio.create_task(manager._collect_streamlink_output(process))
    try:
        await asyncio.sleep(0.01)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        await asyncio.wait_for(manager._collect_streamlink_output(process), timeout=5)
        assert process.returncode == 0
        assert marker.read_bytes() == b"finished"
    finally:
        if process.returncode is None:
            process.kill()
        await manager._collect_streamlink_output(process)
        manager._release_streamlink_output_secrets(process)
