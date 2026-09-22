"""Ownership and deterministic shutdown for application background work."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("streamvault")


@dataclass(frozen=True)
class _TrackedProcess:
    process: asyncio.subprocess.Process
    reaper: Callable[[float], Awaitable[bool]] | None = None


class TaskSupervisor:
    """Own named tasks and child processes until they have been awaited/reaped."""

    def __init__(self, namespace: str) -> None:
        self._namespace = namespace
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._processes: dict[str, _TrackedProcess] = {}
        self._failures: list[tuple[str, str]] = []
        self._shutdown_lock = asyncio.Lock()
        self._shutting_down = False

    @property
    def task_names(self) -> tuple[str, ...]:
        return tuple(self._tasks)

    @property
    def process_names(self) -> tuple[str, ...]:
        return tuple(self._processes)

    @property
    def failures(self) -> tuple[tuple[str, str], ...]:
        for name, task in self._tasks.items():
            if task.done():
                self._observe_task(name, task)
        return tuple(self._failures)

    @property
    def closed(self) -> bool:
        """Whether shutdown has begun and this ownership generation is terminal."""
        return self._shutting_down

    def create_task(
        self, name: str, coroutine: Coroutine[Any, Any, Any]
    ) -> asyncio.Task[Any]:
        """Create a uniquely named task and retain it through shutdown."""
        if self._shutting_down:
            coroutine.close()
            raise RuntimeError("supervisor is shutting down")
        existing = self._tasks.get(name)
        if existing is not None and not existing.done():
            coroutine.close()
            raise RuntimeError(f"task already running: {name}")

        task = asyncio.create_task(coroutine)
        if hasattr(task, "set_name"):
            task.set_name(f"streamvault:{self._namespace}:{name}")
        self._tasks[name] = task
        if hasattr(task, "add_done_callback"):
            task.add_done_callback(
                lambda completed, task_name=name: self._observe_task(
                    task_name, completed
                )
            )
        return task

    def _observe_task(self, name: str, task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        exception = task.exception()
        if exception is None:
            return
        failure = (name, type(exception).__name__)
        if failure not in self._failures:
            self._failures.append(failure)
        logger.error(
            "Background task %s failed (%s)",
            task.get_name(),
            type(exception).__name__,
        )

    def track_process(
        self,
        name: str,
        process: asyncio.subprocess.Process,
        *,
        reaper: Callable[[float], Awaitable[bool]] | None = None,
    ) -> None:
        """Retain ownership of a child process until release or shutdown."""
        if self._shutting_down:
            raise RuntimeError("supervisor is shutting down")
        existing = self._processes.get(name)
        if existing is not None and existing.process.returncode is None:
            raise RuntimeError(f"process already running: {name}")
        self._processes[name] = _TrackedProcess(process=process, reaper=reaper)

    async def release_process(self, name: str, *, already_reaped: bool = False) -> None:
        """Await an already-exiting child and release its supervisor ownership."""
        tracked = self._processes.get(name)
        if tracked is None:
            return
        if not already_reaped:
            await tracked.process.wait()
        if self._processes.get(name) is tracked:
            self._processes.pop(name, None)

    async def shutdown(self, process_timeout: float = 5.0) -> None:
        """Cancel/await tasks and terminate/reap processes, once, in reverse order."""
        async with self._shutdown_lock:
            if self._shutting_down and not self._tasks and not self._processes:
                return
            self._shutting_down = True

            for _name, task in reversed(tuple(self._tasks.items())):
                if not task.done():
                    task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # _observe_task records only the type, never exception text.
                    pass
            self._tasks.clear()

            for name, tracked in reversed(tuple(self._processes.items())):
                reaped = (
                    await tracked.reaper(process_timeout)
                    if tracked.reaper is not None
                    else await self._reap_process(tracked.process, process_timeout)
                )
                if reaped and self._processes.get(name) is tracked:
                    self._processes.pop(name, None)

    @staticmethod
    async def _reap_process(
        process: asyncio.subprocess.Process, timeout: float
    ) -> bool:
        if process.returncode is not None:
            await process.wait()
            return True
        try:
            process.terminate()
        except ProcessLookupError:
            await process.wait()
            return True
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        return process.returncode is not None
