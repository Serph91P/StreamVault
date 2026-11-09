"""Local capture/real registered postprocessing/HTTP comparison, no provider calls.

Run with a target checkout's locked Python and --repo. App routes, authentication,
queue factory and media handlers are real. Uvicorn lifespan is explicitly OFF;
this resource benchmark does not replace the separate full-app/restart gates.
Synthetic capture launch replaces Twitch only. Never pass a configured app DB.
"""

import argparse
import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import tempfile
import time

WRITER = """import os,signal,subprocess,sys,time
child=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-y','-re','-stream_loop','-1','-i',sys.argv[1],'-t',sys.argv[3],'-c','copy','-f','mpegts',sys.argv[2]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
block=b'x'*1023+b'\\n'
signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
try:
 for n in range(256):
  os.write(1,block*32); os.write(2,block*32)
  time.sleep(float(sys.argv[3])/256)
 sys.exit(child.wait())
finally:
 if child.poll() is None: child.kill(); child.wait()
"""


def checksum(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def probe(path):
    info = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration,size",
                "-of",
                "json",
                str(path),
            ],
            text=True,
        )
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-xerror",
            "-nostdin",
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    return {**info["format"], "sha256": checksum(path)}


async def run(args, root):
    from runtime_diagnostics import RuntimeDiagnostics
    import httpx
    import psutil
    import uvicorn
    from app.database import Base, SessionLocal, engine
    from app.models import GlobalSettings, Stream, Streamer, Recording, User
    from app.services.core.auth_service import AuthService
    from app.main import app
    from app.services.background_queue_service import (
        background_queue_service as service,
    )
    from app.services.processing.post_processing_task_handlers import (
        post_processing_task_handlers as handlers,
    )
    from app.services.recording.process_manager import ProcessManager
    from app.utils.security import sanitize_streamlink_output

    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        Base.metadata.create_all(connection)
    fixture = root / "fixture.ts"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=24",
            "-t",
            "6",
            "-c:v",
            "mpeg2video",
            "-b:v",
            "8M",
            "-minrate",
            "8M",
            "-maxrate",
            "8M",
            "-bufsize",
            "16M",
            "-threads",
            "1",
            "-f",
            "mpegts",
            str(fixture),
        ],
        check=True,
    )
    with SessionLocal() as db:
        db.add(GlobalSettings(id=1, notifications_enabled=False))
        db.add(
            User(
                username="local-benchmark",
                password=AuthService(db).hash_password("synthetic-local-only"),
                is_admin=True,
            )
        )
        now = datetime.now(timezone.utc)
        for n in range(args.channels + 1):
            channel = Streamer(username=f"channel-{n}", twitch_id=f"synthetic-{n}")
            db.add(channel)
            db.flush()
            folder = root / f"channel-{n}"
            folder.mkdir()
            source = folder / "input.ts"
            source.write_bytes(fixture.read_bytes())
            stream = Stream(
                streamer_id=channel.id,
                title=f"Synthetic {n}",
                started_at=now - timedelta(seconds=3),
                ended_at=now,
                recording_path=str(source),
            )
            db.add(stream)
            db.flush()
            db.add(
                Recording(
                    id=stream.id,
                    stream_id=stream.id,
                    status="completed",
                    start_time=now,
                    end_time=now,
                    path=str(source),
                )
            )
        db.commit()
    for kind in (
        "metadata_generation",
        "chapters_generation",
        "mp4_remux",
        "mp4_validation",
        "thumbnail_generation",
        "cleanup",
    ):
        service.register_task_handler(kind, getattr(handlers, "handle_" + kind))
    await service.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            lifespan="off",
            log_level="error",
            access_log=False,
        )
    )
    serving = asyncio.create_task(server.serve())
    async with asyncio.timeout(15):
        while not server.started:
            await asyncio.sleep(0.02)
    current = psutil.Process()
    initial_io = current.io_counters()._asdict()
    io_peaks = {}
    metrics = {
        "peak_app_rss_bytes": 0,
        "peak_tree_rss_bytes": 0,
        "peak_children": 0,
        "peak_ffmpeg": 0,
        "peak_ffprobe": 0,
        "peak_postprocessing_ffmpeg": 0,
    }
    stop = asyncio.Event()
    lag = []

    async def sample():
        previous = time.perf_counter()
        while not stop.is_set():
            now = time.perf_counter()
            lag.append(max(0, now - previous - 0.02))
            previous = now
            tree = [current] + current.children(recursive=True)
            rss = 0
            counts = {"ffmpeg": 0, "ffprobe": 0}
            postprocessing = 0
            for process in tree:
                try:
                    size = process.memory_info().rss
                    rss += size
                    if process.pid == current.pid:
                        metrics["peak_app_rss_bytes"] = max(
                            metrics["peak_app_rss_bytes"], size
                        )
                    name = process.name()
                    if name in counts:
                        counts[name] += 1
                    if name == "ffmpeg" and process.ppid() == current.pid:
                        postprocessing += 1
                    io = process.io_counters()._asdict()
                    key = (process.pid, process.create_time())
                    old = io_peaks.get(key, {k: 0 for k in io})
                    io_peaks[key] = {
                        k: max(
                            old[k],
                            v - (initial_io[k] if process.pid == current.pid else 0),
                        )
                        for k, v in io.items()
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            metrics["peak_tree_rss_bytes"] = max(metrics["peak_tree_rss_bytes"], rss)
            metrics["peak_children"] = max(metrics["peak_children"], len(tree) - 1)
            for name, count in counts.items():
                metrics["peak_" + name] = max(metrics["peak_" + name], count)
            metrics["peak_postprocessing_ffmpeg"] = max(
                metrics["peak_postprocessing_ffmpeg"], postprocessing
            )
            await asyncio.sleep(0.02)

    manager = object.__new__(ProcessManager)
    manager._streamlink_output_secrets = {}
    children = []
    outputs = []
    latencies = []
    transfers = []
    ids = []
    playback_tasks = []
    failure = None
    states = {}
    observer = RuntimeDiagnostics(engine)
    start_cpu = resource.getrusage(resource.RUSAGE_SELF)
    start_child = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    sampler = asyncio.create_task(sample())
    try:
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=30
        ) as client:
            login = await client.post(
                "/auth/login",
                json={
                    "username": "local-benchmark",
                    "password": "synthetic-local-only",
                },
            )
            assert login.status_code == 200, login.text

            async def collect(child):
                stdout, stderr = await (
                    manager._collect_streamlink_output(child)
                    if hasattr(manager, "_collect_streamlink_output")
                    else child.communicate()
                )
                safe = [
                    sanitize_streamlink_output(part.decode(errors="replace"), ())
                    for part in (stdout, stderr)
                ]
                assert child.returncode == 0
                return {
                    "stdout_bytes": len(stdout),
                    "stderr_bytes": len(stderr),
                    "sanitized_chars": sum(map(len, safe)),
                }

            for n in range(args.channels):
                child = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-c",
                    WRITER,
                    str(fixture),
                    str(root / f"capture-{n}.ts"),
                    str(args.seconds),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                children.append(child)
                manager._remember_streamlink_output_secrets(child, [])
                outputs.append(asyncio.create_task(collect(child)))
                ids.extend(
                    await service.queue_manager.enqueue_recording_post_processing(
                        stream_id=n + 1,
                        recording_id=n + 1,
                        ts_file_path=str(root / f"channel-{n}" / "input.ts"),
                        output_dir=str(root / f"channel-{n}"),
                        streamer_name=f"channel-{n}",
                        started_at=now.isoformat(),
                        cleanup_ts_file=False,
                    )
                )

            async def playback(n):
                expected = fixture.read_bytes()
                while time.perf_counter() - started < args.seconds:
                    began = time.perf_counter()
                    ranged = len(transfers) % 2 == 1
                    headers = {"Range": "bytes=188-1879"} if ranged else {}
                    body = bytearray()
                    async with client.stream(
                        "GET",
                        f"/api/videos/{args.channels + 1}/stream",
                        headers=headers,
                    ) as response:
                        assert response.status_code == (206 if ranged else 200), (
                            response.status_code
                        )
                        async for chunk in response.aiter_bytes(chunk_size=16384):
                            body.extend(chunk)
                            if n == 0:
                                await asyncio.sleep(0.01)
                    assert bytes(body) == (expected[188:1880] if ranged else expected)
                    latencies.append(time.perf_counter() - began)
                    transfers.append(
                        {"ranged": ranged, "bytes": len(body), "slow": n == 0}
                    )
                    await asyncio.sleep(0.05)

            playback_tasks = [
                asyncio.create_task(playback(n)) for n in range(args.channels)
            ]
            await asyncio.gather(*playback_tasks, *outputs)
            async with asyncio.timeout(90):
                while True:
                    states = {
                        key: service.queue_manager.get_task_status(key) for key in ids
                    }
                    assert all(value is not None for value in states.values())
                    terminal = [
                        value
                        for value in states.values()
                        if value.value in ("completed", "failed")
                    ]
                    if len(terminal) == len(ids):
                        break
                    await asyncio.sleep(0.05)
            assert all(value.value == "completed" for value in states.values()), {
                key: value.value for key, value in states.items()
            }
    except Exception as error:
        failure = type(error).__name__
        states = {key: service.queue_manager.get_task_status(key) for key in ids}
        metrics["status_at_failure"] = {
            key: (value.value if value is not None else "unknown")
            for key, value in states.items()
        }
    finally:
        for task in playback_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*playback_tasks, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.terminate()
                await child.wait()
            manager._release_streamlink_output_secrets(child)
        await asyncio.gather(*outputs, return_exceptions=True)
        await service.stop()
        metrics["status_after_stop"] = {
            key: (value.value if value is not None else "unknown")
            for key in ids
            for value in [service.queue_manager.get_task_status(key)]
        }
        server.should_exit = True
        await serving
        stop.set()
        await sampler
        diagnostics = observer.finish()
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    child_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    metrics.update(
        elapsed_s=time.perf_counter() - started,
        app_cpu_s=cpu.ru_utime + cpu.ru_stime - start_cpu.ru_utime - start_cpu.ru_stime,
        waited_child_cpu_s=child_cpu.ru_utime
        + child_cpu.ru_stime
        - start_child.ru_utime
        - start_child.ru_stime,
        sampled_tree_io={
            k: sum(row[k] for row in io_peaks.values()) for k in initial_io
        },
        looplag_s=lag,
        latency_s=latencies,
        transfers=transfers,
        outputs=[
            task.result()
            if not task.cancelled() and task.exception() is None
            else {
                "error": type(task.exception()).__name__
                if not task.cancelled()
                else "cancelled"
            }
            for task in outputs
        ],
        accepted_ids=ids,
        final_status={
            key: value.value if value is not None else "unknown"
            for key, value in states.items()
        },
        diagnostics=diagnostics,
        logging_state={
            "global_disable": logging.root.manager.disable,
            "streamvault_level": logging.getLogger("streamvault").getEffectiveLevel(),
        },
        failure=failure,
    )
    if failure is not None:
        metrics["partial_capture_files"] = [
            {"bytes": p.stat().st_size, "sha256": checksum(p)}
            for p in sorted(root.glob("capture-*.ts"))
        ]
        return metrics
    metrics["captures"] = [
        probe(root / f"capture-{n}.ts") for n in range(args.channels)
    ]
    metrics["processed"] = [
        probe(root / f"channel-{n}" / "input.mp4") for n in range(args.channels)
    ]
    assert all(
        float(item["duration"]) >= args.seconds - 0.3 for item in metrics["captures"]
    )
    assert all(
        checksum(root / f"channel-{n}" / "input.ts") == checksum(fixture)
        for n in range(args.channels + 1)
    )
    assert not current.children(recursive=True), "owned children survived cleanup"
    if hasattr(manager, "_collect_streamlink_output"):
        assert metrics["peak_postprocessing_ffmpeg"] <= 2
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--channels", type=int, choices=(1, 4, 8), required=True)
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    assert args.seconds >= 3
    sys.path.insert(0, str(args.repo.resolve(strict=True)))
    with tempfile.TemporaryDirectory(prefix="sv-mixed-media-") as temporary:
        root = Path(temporary)
        for key in (
            "LOG_DIR",
            "LOGS_BASE_DIR",
            "APP_LOG_DIR",
            "STREAMLINK_LOG_DIR",
            "FFMPEG_LOG_DIR",
            "RECORDING_DIRECTORY",
            "ARTWORK_BASE_PATH",
        ):
            os.environ[key] = str(root)
        os.environ.update(
            DATABASE_URL=f"sqlite:///{root}/app.db",
            BASE_URL="http://127.0.0.1",
            TWITCH_APP_ID="synthetic-local",
            TWITCH_APP_SECRET="synthetic-local",
            AUTH_JWT_SECRET="synthetic-local-benchmark-key-at-least-32-characters",
            SECURE_COOKIES="false",
            USE_SECURE_COOKIES="false",
        )
        logging.disable(logging.CRITICAL)
        metrics = asyncio.run(run(args, root))
    result = {
        "scope": "real queue factory+six registered handlers, authenticated TCP Full/Range/Slow, synthetic local FFmpeg capture+collector; NOT Twitch/full app lifespan/restart or production disk",
        "repo": str(args.repo),
        "channels": args.channels,
        "seconds": args.seconds,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "io_caveat": "sampled child I/O may miss final exit counters; warm filesystem, no drop_caches; client/server share one process",
        **metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("looplag_s", "latency_s", "transfers")
            },
            indent=2,
        )
    )

    if result.get("failure") is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
