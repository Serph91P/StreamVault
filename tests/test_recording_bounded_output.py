"""Real-child regressions: startup must drain before handing off to monitor."""

import asyncio
import sys

import pytest

from app.services.recording.process_manager import ProcessManager


@pytest.mark.asyncio
async def test_startup_drains_both_pipes_before_monitor_handoff(tmp_path):
    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    marker = tmp_path / "written.ts"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        "import os,sys,time,pathlib; "
        "os.write(2,b'Authorization token invalid\\n'); "
        "[(os.write(1,b'x'*8192),os.write(2,b'y'*8192)) for _ in range(1024)]; "
        "pathlib.Path(sys.argv[1]).write_bytes(b'media-complete'); time.sleep(30)",
        str(marker),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    manager._remember_streamlink_output_secrets(process, [])
    try:
        for _ in range(200):
            if marker.exists():
                break
            await asyncio.sleep(0.01)
        assert marker.exists(), "startup blocked behind undrained child pipes"
        process.terminate()
        stdout, stderr = await manager._collect_streamlink_output(process)
        assert len(stdout) <= 65536
        assert len(stderr) <= 65536
        assert b"Authorization token invalid" in stderr
        assert marker.read_bytes() == b"media-complete"
    finally:
        if process.returncode is None:
            process.kill()
        if process in getattr(manager, "_streamlink_outputs", {}):
            await manager._streamlink_outputs[process].wait()
        else:
            await process.communicate()
        manager._release_streamlink_output_secrets(process)
