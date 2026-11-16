"""Run built REAL onboarding against product routes and disposable SQLite.

Usage: python3 tests/onboarding_acceptance/run.py --output ABSOLUTE_DIRECTORY
Uses the existing local runtime image for installed dependencies, not its sources.
"""

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
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
here = Path(__file__).resolve().parent
frontend = root / "app/frontend"
subprocess.run(
    ["node", "scripts/build-artifact-provenance.mjs", "verify", "--mode", "real"],
    cwd=frontend,
    check=True,
)
provenance = json.loads(
    (frontend / "dist/.streamvault-build-provenance.json").read_text()
)
assert provenance["mode"] == "real"
args.output.mkdir(parents=True, exist_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
name = f"streamvault-995-acceptance-{os.getpid()}"
env = os.environ.copy()
env.update(
    ACCEPTANCE_PASSWORD=secrets.token_urlsafe(32),
    ACCEPTANCE_JWT=secrets.token_urlsafe(48),
    ACCEPTANCE_ORIGIN=f"http://127.0.0.1:{port}",
    ACCEPTANCE_OUTPUT=str(args.output.resolve()),
    FRONTEND_ROOT=str(frontend),
)
with tempfile.TemporaryDirectory(prefix="issue995-", dir=os.environ["TMPDIR"]) as tmp:
    scratch = Path(tmp)
    archive = scratch / "source.tar"
    tracked = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z", "--", "app"], text=True
    ).split("\0")
    with tarfile.open(archive, "w") as tar:
        for relative in tracked:
            if relative and not relative.startswith("app/frontend/"):
                path = root / relative
                if path.is_file() and not path.is_symlink() and ".env" not in path.name:
                    tar.add(path, arcname=relative, recursive=False)
        tar.add(frontend / "dist", arcname="app/frontend/dist")
        tar.add(here / "backend.py", arcname="onboarding_backend.py")
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
        "ENVIRONMENT=test",
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
        f"cd /scratch && tar -xf - && exec python -m uvicorn onboarding_backend:app --host 127.0.0.1 --port {port} --lifespan off",
    ]
    with archive.open("rb") as source, (scratch / "backend.log").open("w+") as log:
        process = subprocess.Popen(
            command, stdin=source, stdout=log, stderr=log, env=env
        )
        try:
            deadline = time.monotonic() + 30
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Backend exited {process.returncode}")
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
                    raise RuntimeError("Backend readiness timed out")
                time.sleep(0.1)
            result = subprocess.run(
                ["node", str(here / "browser.mjs")],
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            print(result.stdout)
            print(result.stderr.replace(env["ACCEPTANCE_PASSWORD"], "[REDACTED]"))
            result.check_returncode()
        except Exception:
            log.flush()
            log.seek(0)
            diagnostic = (
                log.read()
                .replace(env["ACCEPTANCE_PASSWORD"], "[REDACTED]")
                .replace(env["ACCEPTANCE_JWT"], "[REDACTED]")
            )
            print(diagnostic[-6000:])
            raise
        finally:
            subprocess.run(
                ["docker", "stop", "-t", "3", name],
                capture_output=True,
                timeout=15,
                check=False,
            )
            process.wait(timeout=15)
    assert not subprocess.check_output(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        text=True,
    ).strip()
(args.output / "build-provenance.json").write_text(json.dumps(provenance, indent=2))
print("Owned --rm container and disposable SQLite removed.")
