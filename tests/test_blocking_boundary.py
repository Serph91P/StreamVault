"""The hybrid boundary retains its worker until owned resources are closed."""

import asyncio
import threading

import pytest

from app.config.logging_config import request_context
from app.utils.async_db_utils import run_in_thread_pool


@pytest.mark.asyncio
async def test_blocking_boundary_forwards_keywords_and_request_context() -> None:
    token = request_context.set("boundary-request")
    try:

        def operation(*, label: str) -> tuple[str, str | None]:
            return label, request_context.get()

        assert await run_in_thread_pool(operation, label="result") == (
            "result",
            "boundary-request",
        )
    finally:
        request_context.reset(token)


@pytest.mark.asyncio
async def test_blocking_boundary_preserves_request_context_without_keywords() -> None:
    token = request_context.set("boundary-request")
    try:
        assert await run_in_thread_pool(request_context.get) == "boundary-request"
    finally:
        request_context.reset(token)


@pytest.mark.asyncio
async def test_blocking_boundary_propagates_worker_failure() -> None:
    def operation() -> None:
        raise ValueError("synthetic worker failure")

    with pytest.raises(ValueError, match="synthetic worker failure"):
        await run_in_thread_pool(operation)


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_actual_worker_cleanup() -> None:
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    closed = asyncio.Event()
    release = threading.Event()
    event_loop_thread = threading.get_ident()

    def operation() -> None:
        assert threading.get_ident() != event_loop_thread
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(timeout=3)
        finally:
            loop.call_soon_threadsafe(closed.set)

    task = asyncio.create_task(run_in_thread_pool(operation))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "Cancellation abandoned the still-running worker"
        assert not closed.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.wait_for(closed.wait(), 1)
