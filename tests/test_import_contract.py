"""Import boundary contracts for application modules."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_dependencies_imports_in_a_fresh_process() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import app.dependencies"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
