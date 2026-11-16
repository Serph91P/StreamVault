"""Run genuine REAL-build worker upgrades against an isolated original factory.

Usage: .venv/bin/python tests/pwa_update_acceptance/run.py --old DIST --new DIST
--output /opt/data/tmp/hermes-verify-... [--expect-loss]
No production DB, environment file, auth fixture or static response overlay.
"""

import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--old", type=Path, required=True)
parser.add_argument("--new", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--expect-loss", action="store_true")
parser.add_argument("--full", action="store_true")
parser.add_argument(
    "--native-races",
    action="store_true",
    help="Exercise original ApiClient through a test-only source-export accessor",
)
parser.add_argument("--expect-cache-loss", action="store_true")
parser.add_argument(
    "--legacy-source",
    type=Path,
    help="Exact original source export for legacy HTTP-cache population",
)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
for dist in (args.old, args.new):
    assert (
        json.loads((dist / ".streamvault-build-provenance.json").read_text())["mode"]
        == "real"
    )
with tempfile.TemporaryDirectory(
    prefix="hermes-verify-pwa-", dir="/opt/data/tmp"
) as tmp:
    work = Path(tmp)
    frontend = work / "app/frontend"
    frontend.mkdir(parents=True)
    (frontend / "dist").symlink_to(args.old.resolve(), target_is_directory=True)
    (frontend / "public").symlink_to(
        ROOT / "app/frontend/public", target_is_directory=True
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(ROOT) + os.pathsep + str(HERE),
        PYTHON_DOTENV_DISABLED="1",
        ENVIRONMENT="test",
        BASE_DIR=str(work),
        BASE_URL=origin,
        DATABASE_URL=f"sqlite:///{work / 'fixture.sqlite'}",
        TWITCH_APP_ID="synthetic",
        TWITCH_APP_SECRET="synthetic",
        RECORDING_DIRECTORY=str(work / "recordings"),
        ARTWORK_BASE_PATH=str(work / "artwork"),
        LOG_DIR=str(work / "logs"),
        LOGS_BASE_DIR=str(work / "logs"),
        APP_LOG_DIR=str(work / "logs/app"),
        FFMPEG_LOG_DIR=str(work / "logs/ffmpeg"),
        STREAMLINK_LOG_DIR=str(work / "logs/streamlink"),
        PWA_TEST_PASSWORD=secrets.token_urlsafe(24),
        PWA_TEST_JWT=secrets.token_urlsafe(48),
        PWA_TEST_ORIGIN=origin,
        PWA_TEST_FRONTEND=str(frontend),
        PWA_TEST_OLD=str(args.old.resolve()),
        PWA_TEST_NEW=str(args.new.resolve()),
        PWA_TEST_OUTPUT=str(args.output.resolve()),
        PWA_EXPECT_LOSS=str(int(args.expect_loss)),
        PWA_FULL=str(int(args.full)),
        PWA_NATIVE_RACES=str(int(args.native_races)),
        PWA_EXPECT_CACHE_LOSS=str(int(args.expect_cache_loss)),
    )
    if args.legacy_source:
        assert not args.full, "Legacy server switching is only for first migration"
        env["PWA_BACKEND_SWITCH"] = str(work / "backend-switch")
        env["PYTHONPATH"] = str(args.legacy_source.resolve()) + os.pathsep + str(HERE)
    generation = 0
    with (args.output / "backend.log").open("w") as log:

        def start_backend():
            return subprocess.Popen(
                [
                    str(ROOT / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "backend:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--lifespan",
                    "off",
                    "--no-access-log",
                ],
                cwd=work,
                env=env,
                stdout=log,
                stderr=log,
            )

        def wait_ready():
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Factory host exited {process.returncode}; see backend.log"
                    )
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                    conn.request(
                        "GET", "/auth/setup", headers={"Accept": "application/json"}
                    )
                    response = conn.getresponse()
                    ready = (
                        response.status == 200
                        and json.loads(response.read())["setup_required"] is False
                    )
                    conn.close()
                    if ready:
                        break
                except OSError, ValueError, http.client.HTTPException:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("Factory host readiness failed; see backend.log")
                time.sleep(0.1)

        process = start_backend()
        result = None
        try:
            wait_ready()
            with (
                (args.output / "browser.stdout").open("w") as stdout,
                (args.output / "browser.stderr").open("w") as stderr,
            ):
                result = subprocess.Popen(
                    ["node", str(HERE / "browser.mjs")],
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                )
                deadline = time.monotonic() + 300
                last_switch = ""
                while result.poll() is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError("Browser acceptance exceeded 300 seconds")
                    switch = work / "backend-switch"
                    if args.legacy_source and switch.exists():
                        requested = switch.read_text()
                        if requested != last_switch:
                            process.terminate()
                            process.wait(timeout=15)
                            generation += 1
                            source = (
                                args.legacy_source.resolve()
                                if requested.endswith("old")
                                else ROOT
                            )
                            env["PYTHONPATH"] = str(source) + os.pathsep + str(HERE)
                            env["DATABASE_URL"] = (
                                f"sqlite:///{work / ('fixture-' + str(generation) + '.sqlite')}"
                            )
                            process = start_backend()
                            wait_ready()
                            switch.with_suffix(".ready").write_text(requested)
                            last_switch = requested
                    time.sleep(0.05)
            print((args.output / "browser.stdout").read_text())
            if result.returncode:
                print(
                    (args.output / "browser.stderr")
                    .read_text()
                    .replace(env["PWA_TEST_PASSWORD"], "[synthetic-password]")
                    .replace(env["PWA_TEST_JWT"], "[synthetic-key]")
                )
                raise RuntimeError(f"Browser acceptance failed: {result.returncode}")
        finally:
            if result is not None and result.poll() is None:
                result.terminate()
                result.wait(timeout=15)
            process.terminate()
            process.wait(timeout=15)
