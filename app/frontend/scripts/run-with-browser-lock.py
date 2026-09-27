import fcntl
import subprocess
import sys
from pathlib import Path

LOCK = Path("/opt/data/agent/cache/scratch/streamvault-ui-browser-tests.lock")
LOCK.parent.mkdir(parents=True, exist_ok=True)
with LOCK.open("a+") as lock_file:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
    raise SystemExit(subprocess.call(sys.argv[1:]))
