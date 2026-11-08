"""Reproducible synthetic catalog baseline; never uses the configured app DB.

Run with the target checkout's Python and --repo. Results include harness/client
CPU; this in-process HTTP run is not a production or loopback-network benchmark.
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import resource
import sys
import tempfile
import time


def proc_io():
    return {
        key: int(value)
        for key, value in (
            line.split(":", 1)
            for line in Path("/proc/self/io").read_text().splitlines()
        )
    }


def percentile(values, fraction):
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * fraction))]


async def catalog(args, root):
    import httpx
    from fastapi import FastAPI
    from sqlalchemy import create_engine, event, insert
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app.models import ActiveRecordingState, Recording, Stream, Streamer
    from app import dependencies
    from app.routes import videos

    engine = create_engine(
        f"sqlite:///{root / 'catalog.db'}", connect_args={"check_same_thread": False}
    )
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(
            connection,
            tables=[
                model.__table__
                for model in (Streamer, Stream, Recording, ActiveRecordingState)
            ],
        )
    media = root / "shared-synthetic.mp4"
    media.write_bytes(b"synthetic-catalog-only" * 256)
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    with engine.begin() as connection:
        connection.execute(
            insert(Streamer),
            [
                {"id": n, "username": f"channel-{n}", "twitch_id": str(n)}
                for n in range(1, 21)
            ],
        )
        for offset in range(0, args.entries, 1000):
            connection.execute(
                insert(Stream),
                [
                    {
                        "id": n + 1,
                        "streamer_id": n % 20 + 1,
                        "title": f"Stream {n:06}",
                        "twitch_stream_id": str(n),
                        "category_name": f"category-{n % 5}",
                        "recording_path": (None if n % 100 == 1 else str(media))
                        if n % 100
                        else str(root / "missing.mp4"),
                        "started_at": now - timedelta(hours=n),
                        "ended_at": None
                        if n % 100 == 1
                        else now - timedelta(hours=n - 1),
                    }
                    for n in range(offset, min(offset + 1000, args.entries))
                ],
            )
        active_ids = list(range(2, args.entries + 1, 100))
        connection.execute(
            insert(Recording),
            [
                {
                    "id": n,
                    "stream_id": n,
                    "start_time": now - timedelta(minutes=5),
                    "status": "recording",
                }
                for n in active_ids
            ],
        )
        connection.execute(
            insert(ActiveRecordingState),
            [
                {
                    "stream_id": n,
                    "recording_id": n,
                    "process_id": os.getpid(),
                    "process_identifier": f"synthetic-{n}",
                    "streamer_name": f"channel-{(n - 1) % 20 + 1}",
                    "started_at": now - timedelta(minutes=5),
                    "last_heartbeat": now,
                    "ts_output_path": str(media),
                    "status": "active",
                }
                for n in active_ids
            ],
        )
    sessions = sessionmaker(bind=engine)
    from app.services.media.video_catalog_service import VideoCatalogService

    cold_index = None
    lifecycle = None
    if hasattr(VideoCatalogService, "reconcile_batch"):
        from app.models.video_catalog import VideoCatalogEntry

        VideoCatalogEntry.__table__.create(engine)
        before_index, index_io, index_start = (
            resource.getrusage(resource.RUSAGE_SELF),
            proc_io(),
            time.perf_counter(),
        )
        cursor = processed = 0
        while True:
            with sessions() as db:
                cursor, count = VideoCatalogService(db).reconcile_batch(after_id=cursor)
            processed += count
            if not count:
                break
        after_index, after_index_io = (
            resource.getrusage(resource.RUSAGE_SELF),
            proc_io(),
        )
        assert processed == args.entries
        cold_index = {
            "rows": processed,
            "elapsed_s": time.perf_counter() - index_start,
            "cpu_s": after_index.ru_utime
            + after_index.ru_stime
            - before_index.ru_utime
            - before_index.ru_stime,
            "io_delta": {key: after_index_io[key] - index_io[key] for key in index_io},
        }
        videos.SessionLocal = sessions
    application = FastAPI()
    application.include_router(videos.router)

    def fresh_db():
        with sessions() as db:
            yield db

    application.dependency_overrides[dependencies.get_db] = fresh_db
    application.dependency_overrides[dependencies.get_current_identity] = lambda: (
        dependencies.AuthIdentity(
            subject="synthetic-performance",
            roles=frozenset(),
            scopes=frozenset(),
            auth_method="legacy-session",
            interactive=True,
        )
    )
    queries = 0

    @event.listens_for(engine, "before_cursor_execute")
    def count_sql(*_):
        nonlocal queries
        queries += 1

    lifecycle_counts = {"batches": 0, "rows": 0, "cycles": 0}
    if cold_index is not None:
        original_batch = VideoCatalogService.reconcile_batch

        def measured_batch(service, *args, **kwargs):
            result = original_batch(service, *args, **kwargs)
            lifecycle_counts["batches"] += 1
            lifecycle_counts["rows"] += result[1]
            lifecycle_counts["cycles"] += int(result[1] == 0)
            return result

        VideoCatalogService.reconcile_batch = measured_batch

    lag = []
    running = True

    async def heartbeat():
        while running:
            start = time.perf_counter()
            await asyncio.sleep(0.01)
            lag.append(max(0.0, time.perf_counter() - start - 0.01))

    durations, response_sizes, item_counts = [], [], []
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://synthetic.local",
    ) as client:
        warmup = await client.get(args.endpoint)
        warmup.raise_for_status()
        if cold_index is not None:
            payload = warmup.json()
            assert (
                len(payload["items"]) <= 50
                and payload["total"] == args.entries - args.entries // 100
            )
            import app.lifespan as lifespan

            lifespan.SessionLocal = sessions
            lifecycle = asyncio.create_task(lifespan._run_catalog_reconciliation())
        queries = 0
        before_io = proc_io()
        before = resource.getrusage(resource.RUSAGE_SELF)
        start = time.perf_counter()
        ticker = asyncio.create_task(heartbeat())

        async def request(n):
            async with semaphore:
                request_start = time.perf_counter()
                response = await client.get(
                    args.endpoint,
                    params={
                        "page_size": 50,
                        "limit": 50,
                        "sort": ["date", "title", "streamer", "duration", "size"][
                            n % 5
                        ],
                        "page": n % 3 + 1,
                        "q": "Stream 0" if n % 2 else "",
                    },
                )
                response.raise_for_status()
                durations.append(time.perf_counter() - request_start)
                response_sizes.append(len(response.content))
                payload = response.json()
                item_counts.append(
                    len(payload if isinstance(payload, list) else payload["items"])
                )

        try:
            await asyncio.gather(*(request(n) for n in range(args.repeats)))
        finally:
            running = False
            await ticker
            if lifecycle is not None:
                lifecycle.cancel()
                try:
                    await lifecycle
                except asyncio.CancelledError:
                    pass
        elapsed = time.perf_counter() - start
        after = resource.getrusage(resource.RUSAGE_SELF)
        after_io = proc_io()
    api_queries = queries
    api_lifecycle = dict(lifecycle_counts)
    idle = None
    if args.idle_seconds:
        import psutil

        idle_before = resource.getrusage(resource.RUSAGE_SELF)
        idle_io = proc_io()
        idle_queries = queries
        idle_counts = dict(lifecycle_counts)
        idle_started = time.perf_counter()
        idle_rss = 0
        idle_lag = []
        if cold_index is not None:
            lifecycle = asyncio.create_task(lifespan._run_catalog_reconciliation())
        try:
            while time.perf_counter() - idle_started < args.idle_seconds:
                stamp = time.perf_counter()
                await asyncio.sleep(0.1)
                idle_lag.append(max(0, time.perf_counter() - stamp - 0.1))
                idle_rss = max(idle_rss, psutil.Process().memory_info().rss)
        finally:
            if lifecycle is not None:
                lifecycle.cancel()
                try:
                    await lifecycle
                except asyncio.CancelledError:
                    pass
        idle_after = resource.getrusage(resource.RUSAGE_SELF)
        idle_after_io = proc_io()
        idle = {
            "scope": "fresh native catalog-reconciliation loop only; no HTTP/whole-app workers, warm synthetic shared file",
            "elapsed_s": time.perf_counter() - idle_started,
            "cpu_s": idle_after.ru_utime
            + idle_after.ru_stime
            - idle_before.ru_utime
            - idle_before.ru_stime,
            "sampled_peak_rss_bytes": idle_rss,
            "sql_count": queries - idle_queries,
            "io_delta": {key: idle_after_io[key] - idle_io[key] for key in idle_io},
            "lifecycle": {
                key: lifecycle_counts[key] - idle_counts[key] for key in idle_counts
            },
            "looplag_s": idle_lag,
        }
    engine.dispose()
    return {
        "workload": "catalog-asgi-sqlite",
        "repo": str(args.repo),
        "entries": args.entries,
        "concurrency": args.concurrency,
        "repeats": args.repeats,
        "endpoint": args.endpoint,
        "elapsed_s": elapsed,
        "latency_s": durations,
        "response_bytes": response_sizes,
        "item_counts": item_counts,
        "sql_count": api_queries,
        "lifecycle": api_lifecycle,
        "idle": idle,
        "cold_index": cold_index,
        "lifecycle_reconciler_running": cold_index is not None,
        "fixture_active_count": len(active_ids),
        "looplag_s": lag,
        "latency_p50_s": percentile(durations, 0.50),
        "latency_p95_s": percentile(durations, 0.95),
        "latency_p99_s": percentile(durations, 0.99),
        "looplag_max_s": max(lag, default=0),
        "cpu_user_s": after.ru_utime - before.ru_utime,
        "cpu_system_s": after.ru_stime - before.ru_stime,
        "peak_rss_kib": after.ru_maxrss,
        "io_delta": {key: after_io[key] - before_io[key] for key in before_io},
        "limitations": [
            "ASGI in-process, no TCP",
            "interactive identity overridden for performance only",
            "CPU/I/O includes HTTP client; lifetime RSS also includes fixture/index setup",
            "shared synthetic file, warm filesystem",
            "1% missing, 1% synthetic active, rest completed; not a capture workload",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--entries", type=int, choices=(100, 10000, 50000), default=10000
    )
    parser.add_argument("--concurrency", type=int, choices=(1, 8), default=1)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--idle-seconds", type=int, default=0, choices=range(0, 601))
    parser.add_argument("--endpoint", default="/api/videos?limit=50")
    args = parser.parse_args()
    args.repo = args.repo.resolve(strict=True)
    sys.path.insert(0, str(args.repo))
    with tempfile.TemporaryDirectory(prefix="sv-perf-catalog-") as temporary:
        root = Path(temporary)
        for key in (
            "LOG_DIR",
            "STREAMLINK_LOG_DIR",
            "FFMPEG_LOG_DIR",
            "APP_LOG_DIR",
            "LOGS_BASE_DIR",
            "RECORDING_DIRECTORY",
            "ARTWORK_BASE_PATH",
        ):
            os.environ[key] = str(root / key.lower())
            Path(os.environ[key]).mkdir()
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        os.environ["BASE_URL"] = "http://127.0.0.1:8000"
        os.environ["TWITCH_APP_ID"] = "synthetic-local-only"
        os.environ["TWITCH_APP_SECRET"] = "synthetic-local-only"
        logging.disable(logging.CRITICAL)
        result = asyncio.run(catalog(args, root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key
                not in {"latency_s", "response_bytes", "item_counts", "looplag_s"}
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
