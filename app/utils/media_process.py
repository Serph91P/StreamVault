"""Process-wide post-processing admission; capture/live deliberately bypass it."""

import asyncio
import os
import sys
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any, AsyncIterator, Literal, overload

from app.utils.process_output import BoundedStreamlinkOutput
from app.utils.queue_ownership import queue_owner_fd

# Separate budgets: a stalled remux must not consume all cheap probe capacity.
HEAVY_PROCESS_LIMIT = 2
PROBE_PROCESS_LIMIT = 4
_BUDGETS = {
    "heavy": BoundedSemaphore(HEAVY_PROCESS_LIMIT),
    "probe": BoundedSemaphore(PROBE_PROCESS_LIMIT),
}


async def _drain_owned(task):
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


@overload
def media_process(
    *command: str,
    kind: str | None = None,
    drain: Literal[True] = True,
    launch_timeout: float | None = None,
    **kwargs: Any,
) -> AbstractAsyncContextManager[
    tuple[asyncio.subprocess.Process, BoundedStreamlinkOutput]
]: ...


@overload
def media_process(
    *command: str,
    kind: str | None = None,
    drain: Literal[False],
    launch_timeout: float | None = None,
    **kwargs: Any,
) -> AbstractAsyncContextManager[tuple[asyncio.subprocess.Process, None]]: ...


@asynccontextmanager
async def media_process(
    *command: str,
    kind: str | None = None,
    drain: bool = True,
    launch_timeout: float | None = None,
    **kwargs: Any,
) -> AsyncIterator[tuple[asyncio.subprocess.Process, BoundedStreamlinkOutput | None]]:
    """Hold admission until child exit and pipe cleanup, including launch cancellation.

    ``drain=False`` is reserved for the progress tracker, which owns its readers.
    No executor threads are occupied waiting for a process slot.
    """
    budget = _BUDGETS[
        kind or ("probe" if Path(command[0]).name == "ffprobe" else "heavy")
    ]
    while not budget.acquire(blocking=False):
        await asyncio.sleep(0.05)
    process = output = None
    launch = None
    try:
        kwargs.setdefault("stdout", asyncio.subprocess.PIPE)
        kwargs.setdefault("stderr", asyncio.subprocess.PIPE)
        owner_fd = queue_owner_fd.get()
        if os.name == "posix" and owner_fd is not None:
            kwargs["pass_fds"] = (*kwargs.get("pass_fds", ()), owner_fd)
        if sys.platform == "linux":
            command = (
                sys.executable,
                "-I",
                "-S",
                str(Path(__file__).with_name("_parent_owned_exec.py")),
                str(os.getpid()),
                *command,
            )
        launch = asyncio.create_task(asyncio.create_subprocess_exec(*command, **kwargs))
        process = await asyncio.wait_for(asyncio.shield(launch), timeout=launch_timeout)
        if drain:
            output = BoundedStreamlinkOutput(process)
        yield process, output
    finally:

        async def cleanup():
            nonlocal process
            if process is None and launch is not None:
                process = await launch
            if process is not None:
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                if output is not None:
                    await output.wait()
                else:
                    await process.communicate()

        try:
            await _drain_owned(asyncio.create_task(cleanup()))
        finally:
            budget.release()
