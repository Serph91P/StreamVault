"""Supervisor for a real Uvicorn process restart with retained disposable DB."""

import os
from pathlib import Path
import signal
import subprocess
import time

child = None
stopping = False


def stop(_signum, _frame):
    global stopping
    stopping = True
    if child and child.poll() is None:
        child.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    while not stopping:
        child = subprocess.Popen(
            [
                "python",
                "-m",
                "uvicorn",
                "browser_acceptance_backend:app",
                "--host",
                "127.0.0.1",
                "--port",
                os.environ["ACCEPTANCE_PORT"],
                "--lifespan",
                "off",
                "--log-level",
                "error",
                "--no-access-log",
            ]
        )
        while child.poll() is None and not stopping:
            if Path("/scratch/restart-requested").exists():
                # Let the authenticated request finish, then terminate the actual process.
                time.sleep(0.3)
                Path("/scratch/restart-requested").unlink()
                Path("/scratch/restarted").touch()
                child.terminate()
                child.wait(timeout=15)
                break
            time.sleep(0.05)
        if child.poll() not in (0, -signal.SIGTERM, None):
            raise SystemExit(child.returncode)
        if not Path("/scratch/restarted").exists():
            break
finally:
    if child and child.poll() is None:
        child.terminate()
        child.wait(timeout=15)
