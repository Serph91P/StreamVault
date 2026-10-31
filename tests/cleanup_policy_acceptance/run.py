"""Run against a built REAL frontend and a disposable local product backend.

Usage: uv run python tests/cleanup_policy_acceptance/run.py --output PATH
Optional --frontend PATH exercises a temporary integration's built frontend.
"""

import argparse
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--frontend", type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
here = Path(__file__).resolve().parent
frontend = (args.frontend or repo / "app/frontend").resolve()
provenance = json.loads(
    (frontend / "dist/.streamvault-build-provenance.json").read_text()
)
assert provenance["mode"] == "real"
args.output.mkdir(parents=True, exist_ok=True)
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
with tempfile.TemporaryDirectory(prefix="policy-947-", dir=os.environ["TMPDIR"]) as tmp:
    scratch = Path(tmp)
    static = scratch / "app/frontend"
    static.mkdir(parents=True)
    (static / "dist").symlink_to(frontend / "dist", target_is_directory=True)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": os.pathsep.join([str(here), str(repo)]),
            "DATABASE_URL": f"sqlite:///{scratch / 'acceptance.sqlite'}",
            "BASE_URL": f"http://127.0.0.1:{port}",
            "LOG_DIR": str(scratch / "logs"),
            "RECORDING_DIRECTORY": str(scratch / "recordings"),
            "TWITCH_APP_ID": "synthetic",
            "TWITCH_APP_SECRET": "synthetic",
            "ACCEPTANCE_JWT": secrets.token_urlsafe(48),
            "ACCEPTANCE_PASSWORD": secrets.token_urlsafe(32),
            "FRONTEND_ROOT": str(frontend),
            "ACCEPTANCE_ORIGIN": f"http://127.0.0.1:{port}",
            "ACCEPTANCE_OUTPUT": str(args.output.resolve()),
        }
    )
    for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
        env[key] = str(scratch / key)
    with (scratch / "backend.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--lifespan",
                "off",
                "--log-level",
                "error",
            ],
            cwd=scratch,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 30
            diagnostic = "no HTTP response"
            while True:
                assert process.poll() is None, "isolated backend exited"
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                    conn.request(
                        "GET", "/auth/setup", headers={"Accept": "application/json"}
                    )
                    response = conn.getresponse()
                    body = response.read()
                    ready = (
                        response.status == 200
                        and not json.loads(body)["setup_required"]
                    )
                    diagnostic = f"HTTP {response.status}: {body[:300]!r}"
                    conn.close()
                    if ready:
                        break
                except OSError, ValueError, http.client.HTTPException:
                    pass
                assert time.monotonic() < deadline, (
                    f"backend readiness timeout: {diagnostic}"
                )
                time.sleep(0.1)
            subprocess.run(
                ["node", str(here / "browser.mjs")], env=env, check=True, timeout=240
            )
            (args.output / "build-provenance.json").write_text(
                json.dumps(provenance, indent=2)
            )
        finally:
            process.terminate()
            process.wait(timeout=10)
            # Generated credentials/runtime logs are never retained.
print("Owned backend stopped; disposable database removed; no cleanup/delete invoked.")
