"""A new interpreter must replay missing effects, not replay committed chapters."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("kind", ["stream.online", "stream.offline", "channel.update"])
def test_signed_delivery_survives_full_interpreter_restart(tmp_path, kind):
    worker = Path(__file__).with_name("fixtures") / "issue1029_restart_worker.py"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = (
        str(worker.resolve().parents[2])
        + os.pathsep
        + environment.get("PYTHONPATH", "")
    )
    for phase in ("fail", "retry"):
        result = subprocess.run(
            [sys.executable, str(worker), str(tmp_path), kind, phase],
            env=environment,
            text=True,
            capture_output=True,
            timeout=40,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f'"phase": "{phase}"' in result.stdout
