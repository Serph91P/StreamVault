"""Application-owned recovery controls and cancellation-safe child ownership."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import TypedDict

from app.services.system.supervisor import TaskSupervisor

DEFAULT_RECOVERY_INTERVAL = 300


class RecoveryStatistics(TypedDict):
    total_runs: int
    successful_runs: int
    failed_runs: int
    last_error: str | None


class AutomatedRecoveryState:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._running = False
        self._interval = DEFAULT_RECOVERY_INTERVAL
        self._last_run: datetime | None = None
        self._stats: RecoveryStatistics = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "last_error": None,
        }
        self._task: asyncio.Task[None] | None = None

    async def is_running(self) -> bool:
        async with self._lock:
            return self._running

    async def set_running(self, running: bool) -> None:
        async with self._lock:
            self._running = running

    async def get_interval(self) -> int:
        async with self._lock:
            return self._interval

    async def set_interval(self, interval: int) -> None:
        async with self._lock:
            self._interval = interval

    async def get_last_run(self) -> datetime | None:
        async with self._lock:
            return self._last_run

    async def set_last_run(self, timestamp: datetime) -> None:
        async with self._lock:
            self._last_run = timestamp

    async def get_stats(self) -> RecoveryStatistics:
        async with self._lock:
            return self._stats.copy()

    async def increment_total_runs(self) -> None:
        async with self._lock:
            self._stats["total_runs"] += 1

    async def increment_successful_runs(self) -> None:
        async with self._lock:
            self._stats["successful_runs"] += 1
            self._stats["last_error"] = None

    async def increment_failed_runs(self, error: str) -> None:
        async with self._lock:
            self._stats["failed_runs"] += 1
            self._stats["last_error"] = error

    async def set_task(self, task: asyncio.Task[None] | None) -> None:
        async with self._lock:
            self._task = task

    async def get_task(self) -> asyncio.Task[None] | None:
        async with self._lock:
            return self._task

    async def start(
        self,
        supervisor: TaskSupervisor,
        operation: Callable[[], Coroutine[object, object, None]],
        interval: int,
    ) -> bool:
        async with self._lock:
            if self._running or (self._task is not None and not self._task.done()):
                return False
            task = supervisor.create_task("automated-recovery", operation())
            self._interval = interval
            self._task = task
            self._running = True
            return True

    async def cancel_task(self) -> None:
        async with self._lock:
            task = self._task
            self._running = False
            if task is not None and not task.done() and not task.cancelling():
                task.cancel()
        if task is None:
            return
        cancelled = False
        try:
            while True:
                try:
                    await asyncio.shield(task)
                    break
                except asyncio.CancelledError:
                    caller = asyncio.current_task()
                    cancelled |= caller is not None and caller.cancelling() > 0
                    if task.done():
                        break
        finally:
            # The child may acquire this lock during its own finalization.
            async with self._lock:
                if self._task is task:
                    self._task = None
        if cancelled:
            raise asyncio.CancelledError
