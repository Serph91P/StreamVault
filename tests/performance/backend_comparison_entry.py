"""Isolated benchmark ingress. Never deployed; only a fresh loopback test PG DB.

The runner places this byte-identical file beside each source snapshot and starts
Uvicorn with the ordinary app lifespan. External networking is disabled by Docker.
Instrumentation adds SQL counters and three explicitly synthetic local workloads;
all ordinary read/auth/EventSub endpoints remain the original production routes.
"""

import asyncio
from contextvars import ContextVar
import os

import time

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url

from fastapi import APIRouter, Request


def load_app():
    url = make_url(os.environ["DATABASE_URL"])
    assert url.get_backend_name() == "postgresql" and url.host == "127.0.0.1"
    assert (url.database or "").startswith("streamvault_test_842_bench_")
    assert os.environ["STREAMVAULT_ISOLATED_BENCHMARK"] == "1"
    from app.main import app

    return app


app = load_app()
queries: ContextVar[list[float] | None] = ContextVar("benchmark_queries", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def before_sql(connection, cursor, statement, parameters, context, executemany):
    context._benchmark_started = time.perf_counter()


@event.listens_for(Engine, "after_cursor_execute")
def after_sql(connection, cursor, statement, parameters, context, executemany):
    samples = queries.get()
    if samples is not None:
        samples.append(time.perf_counter() - context._benchmark_started)


@app.middleware("http")
async def sql_metrics(request, call_next):
    samples = []
    token = queries.set(samples)
    try:
        response = await call_next(request)
        response.headers["x-benchmark-query-count"] = str(len(samples))
        response.headers["x-benchmark-query-seconds"] = str(sum(samples))
        return response
    finally:
        queries.reset(token)


router = APIRouter(prefix="/api/__benchmark")


@router.get("/resources")
async def resources():
    import psutil

    process = psutil.Process()
    return {
        "rss_bytes": process.memory_info().rss,
        "fds": process.num_fds(),
        "tasks": len(asyncio.all_tasks()),
    }


@router.post("/broadcast")
async def broadcast(request: Request):
    # Compatibility app uses the canonical manager on both sides of the change.
    manager = getattr(app.state, "websocket_manager", None)
    if manager is None:
        from app.dependencies import get_websocket_manager

        manager = get_websocket_manager()
    await manager.send_notification(
        {
            "type": "benchmark.event",
            "data": {"sequence": int(request.query_params["sequence"])},
        }
    )
    return {"accepted": True}


@router.post("/queue")
async def queue_workload():
    queue = getattr(app.state, "background_queue_service", None)
    if queue is None:
        from app.services.background_queue_service import background_queue_service

        queue = background_queue_service
    completed = 0
    finished = asyncio.Event()

    async def handler(payload, progress_callback=None):
        nonlocal completed
        completed += 1
        if completed == 100:
            finished.set()
        return True

    queue.register_task_handler("benchmark_noop", handler)
    started = time.perf_counter()
    ids = [
        await queue.enqueue_task("benchmark_noop", {"sequence": n}, max_retries=0)
        for n in range(100)
    ]
    await asyncio.wait_for(finished.wait(), timeout=30)
    elapsed = time.perf_counter() - started
    return {
        "completed": completed,
        "unique_ids": len(set(ids)),
        "seconds": elapsed,
        "jobs_per_second": completed / elapsed,
    }


@router.post("/child")
async def child_workload():
    # The same synthetic capture command is used on both sides: acknowledged
    # native process startup and reaping, not authenticated Twitch admission.
    import sys

    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        'print("ready", flush=True)',
        stdout=asyncio.subprocess.PIPE,
    )
    output, _ = await process.communicate()
    assert output == b"ready\n" and process.returncode == 0
    return {"startup_and_reap_seconds": time.perf_counter() - started}


@router.post("/profile")
async def profile_read_hotspot(request: Request):
    import cProfile
    import io
    import pstats
    import httpx

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        async with httpx.AsyncClient(
            base_url="http://127.0.0.1:7000",
            headers={"Authorization": request.headers["Authorization"]},
        ) as client:
            for _ in range(10):
                response = await client.get("/api/videos/catalog?page=1&page_size=50")
                response.raise_for_status()
                assert len(response.json()["items"]) == 50
    finally:
        profiler.disable()
    output = io.StringIO()
    pstats.Stats(profiler, stream=output).sort_stats("cumulative").print_stats(
        "/app/app/", 25
    )
    return {
        "scope": "ten actual authenticated catalog HTTP requests; event-loop thread cProfile only; worker SQL duration is measured separately",
        "profile": output.getvalue(),
    }


@router.post("/recording-process")
async def recording_process_workload():
    import importlib
    from pathlib import Path
    import sys
    from types import SimpleNamespace
    from datetime import datetime, timezone

    module = importlib.import_module("app.services.recording.process_manager")
    manager = app.state.recording_manager.process_manager
    native_command = module.get_streamlink_command
    outputs = []

    def capture_command(*args, **kwargs):
        path = kwargs["output_path"]
        outputs.append(Path(path))
        return [
            sys.executable,
            "-u",
            "-c",
            'from pathlib import Path; import sys,time; Path(sys.argv[1]).write_bytes(b"synthetic capture acknowledgement"); time.sleep(30)',
            path,
        ]

    # Only the provider executable is substituted; native token resolution,
    # admission, per-owner actor start, logging, supervision and cleanup execute.
    module.get_streamlink_command = capture_command
    process = None
    started = time.perf_counter()
    try:
        stream = SimpleNamespace(
            id=1,
            streamer_id=1,
            title="Benchmark",
            category_name="Synthetic",
            started_at=datetime.now(timezone.utc),
            streamer=SimpleNamespace(username="channel-1", twitch_id="synthetic-1"),
        )
        process = await manager.start_recording_process(
            stream, "/recordings/benchmark-capture.ts", "best"
        )
        assert process is not None

        async def acknowledged():
            while not outputs or not await asyncio.to_thread(outputs[0].exists):
                await asyncio.sleep(0.001)

        await asyncio.wait_for(acknowledged(), timeout=5)
        elapsed = time.perf_counter() - started
    finally:
        module.get_streamlink_command = native_command
        await manager.cleanup_all()
    assert process.returncode is not None
    return {
        "acknowledged_startup_seconds": elapsed,
        "reaped": True,
        "provider": "synthetic acknowledged native child; no authenticated Twitch",
    }


# Keep the benchmark-only routes ahead of the original terminal SPA catch-all.
app.router.routes[0:0] = router.routes
