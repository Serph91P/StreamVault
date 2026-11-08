"""One admission budget across unrelated post-processing launchers, not captures."""

import asyncio
import os
import sys

import pytest


@pytest.mark.asyncio
async def test_global_heavy_admission_and_separate_probe_budget():
    from app.utils.media_process import media_process

    active = peak = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def heavy():
        nonlocal active, peak
        async with media_process(
            sys.executable, "-c", "import time; time.sleep(30)"
        ) as (process, output):
            active += 1
            peak = max(peak, active)
            if active == 2:
                started.set()
            try:
                await release.wait()
            finally:
                active -= 1
                process.terminate()
                await output.wait()

    jobs = [asyncio.create_task(heavy()) for _ in range(12)]
    try:
        await asyncio.wait_for(started.wait(), 3)
        assert peak == 2
        # Neither cheap probes nor capture's native launcher wait behind heavy jobs.
        async with media_process(
            sys.executable, "-c", "print('probe')", kind="probe"
        ) as (_, output):
            stdout, _ = await asyncio.wait_for(output.wait(), 2)
            assert stdout.strip() == b"probe"
        capture = await asyncio.create_subprocess_exec(
            sys.executable, "-c", "print('capture')", stdout=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(capture.communicate(), 2)
        assert stdout.strip() == b"capture"
        release.set()
        await asyncio.wait_for(asyncio.gather(*jobs), 5)
        assert peak == 2
    finally:
        release.set()
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_waiter_launch_window_and_running_child_release_slots(monkeypatch):
    from app.utils.media_process import media_process

    native = asyncio.create_subprocess_exec
    children = []
    launched = asyncio.Event()
    handoff = asyncio.Event()

    async def delayed_launch(*args, **kwargs):
        process = await native(*args, **kwargs)
        children.append(process)
        launched.set()
        await handoff.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_launch)

    async def run():
        async with media_process(
            sys.executable, "-c", "import time; time.sleep(30)"
        ) as (_, output):
            await output.wait()

    job = asyncio.create_task(run())
    try:
        await asyncio.wait_for(launched.wait(), 3)
        job.cancel()
        handoff.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(job, 3)
        assert children[0].returncode is not None
        with pytest.raises(ProcessLookupError):
            os.kill(children[0].pid, 0)
        monkeypatch.setattr(asyncio, "create_subprocess_exec", native)
        async with media_process(sys.executable, "-c", "print('reused')") as (
            _,
            output,
        ):
            assert (await output.wait())[0].strip() == b"reused"
    finally:
        handoff.set()
        job.cancel()
        await asyncio.gather(job, return_exceptions=True)
        for process in children:
            if process.returncode is None:
                process.kill()
            await process.communicate()
