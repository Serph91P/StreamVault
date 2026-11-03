"""Run the real #933 browser slice without writing in either product worktree.

Usage: python run.py --backend REPO --frontend REPO/app/frontend --output DIRECTORY
The existing frontend dist must be a REAL build. Browser APIs are never fulfilled.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tarfile
import tempfile
import time

parser = argparse.ArgumentParser()
parser.add_argument("--backend", type=Path, required=True)
parser.add_argument("--frontend", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
here = Path(__file__).resolve().parent
provenance = json.loads(
    (args.frontend / "dist/.streamvault-build-provenance.json").read_text()
)
assert provenance["mode"] == "real", "A MOCK dist is not valid for this acceptance"
args.output.mkdir(parents=True, exist_ok=True)
(args.output / "result.json").unlink(missing_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
name = f"streamvault-933-owner-browser-{os.getpid()}"
env = os.environ.copy()
env["ACCEPTANCE_PASSWORD"] = secrets.token_urlsafe(32)
env["ACCEPTANCE_JWT"] = secrets.token_urlsafe(48)
env["FRONTEND_ROOT"] = str(args.frontend.resolve())
env["ACCEPTANCE_ORIGIN"] = f"http://127.0.0.1:{port}"
env["ACCEPTANCE_OUTPUT"] = str(args.output.resolve())
with tempfile.TemporaryDirectory(
    prefix="streamvault-933-browser-", dir=os.environ["TMPDIR"]
) as tmp:
    scratch = Path(tmp)
    for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
        value = scratch / key.lower()
        value.mkdir()
        env[key] = str(value)
    archive = scratch / "candidate.tar"
    tracked = subprocess.check_output(
        ["git", "-C", str(args.backend), "ls-files", "-z", "--", "app"], text=True
    ).split("\0")
    with tarfile.open(archive, "w") as tar:
        for relative in tracked:
            if not relative or relative.startswith("app/frontend/"):
                continue
            path = args.backend / relative
            if path.is_file() and not path.is_symlink() and ".env" not in path.name:
                tar.add(path, arcname=relative, recursive=False)
        tar.add(args.frontend / "dist", arcname="app/frontend/dist")
        tar.add(here / "backend.py", arcname="browser_acceptance_backend.py")
        tar.add(here / "supervisor.py", arcname="supervisor.py")
    command = [
        "docker",
        "run",
        "--rm",
        "-i",
        "--name",
        name,
        "--network",
        "container:hermes-gateway-developer",
        "--entrypoint",
        "sh",
        "--tmpfs",
        "/scratch",
        "-e",
        "ACCEPTANCE_PASSWORD",
        "-e",
        "ACCEPTANCE_JWT",
        "-e",
        "PYTHONPATH=/scratch",
        "-e",
        "TMPDIR=/scratch",
        "-e",
        "DATABASE_URL=sqlite:////scratch/acceptance.sqlite",
        "-e",
        f"ACCEPTANCE_PORT={port}",
        "-e",
        "TWITCH_APP_ID=synthetic",
        "-e",
        "TWITCH_APP_SECRET=synthetic",
        "-e",
        f"BASE_URL=http://127.0.0.1:{port}",
        "-e",
        "LOG_DIR=/scratch/logs",
        "-e",
        "RECORDING_DIRECTORY=/scratch/recordings",
        "frequency2098/streamvault:2.24.0-dev",
        "-c",
        "cd /scratch && tar -xf - && exec python supervisor.py",
    ]
    log_path = scratch / "backend.log"
    with archive.open("rb") as source, log_path.open("w") as log:
        process = subprocess.Popen(
            command, stdin=source, stdout=log, stderr=log, env=env
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"isolated backend exited: {process.returncode}")
                try:
                    connection = http.client.HTTPConnection(
                        "127.0.0.1", port, timeout=1
                    )
                    connection.request(
                        "GET", "/auth/setup", headers={"Accept": "application/json"}
                    )
                    response = connection.getresponse()
                    ready = (
                        response.status == 200
                        and json.loads(response.read())["setup_required"] is False
                    )
                    connection.close()
                    if ready:
                        break
                except OSError, ValueError, http.client.HTTPException:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("isolated backend did not become ready")
                time.sleep(0.1)
            completed = subprocess.run(
                ["node", str(here / "browser.mjs")],
                env=env,
                text=True,
                capture_output=True,
                timeout=420,
            )
            print(completed.stdout)
            if completed.returncode:
                print(
                    completed.stderr.replace(env["ACCEPTANCE_PASSWORD"], "[REDACTED]")
                )
                raise RuntimeError(f"browser acceptance exited: {completed.returncode}")
            (args.output / "build-provenance.json").write_text(
                json.dumps(provenance, indent=2)
            )
        except Exception:
            log.flush()
            diagnostic = log_path.read_text().replace(
                env["ACCEPTANCE_PASSWORD"], "[REDACTED]"
            )
            # This isolated app has generated auth only; never retain its raw runtime log.
            print("Isolated backend diagnostic:\n" + diagnostic[-5000:])
            raise
        finally:
            subprocess.run(
                ["docker", "stop", "-t", "5", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
            process.wait(timeout=15)
    remaining = subprocess.check_output(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        text=True,
    )
    assert not remaining.strip(), "owned --rm test container was not removed"
    print("Owned test container removed; no product worktree changed.")
