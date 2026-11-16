"""Owner #900 RED: real initialized factory, no auth/route/dependency shortcuts."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_logged_out_factory_serves_exact_precache_icons_without_opening_lookalikes(
    tmp_path,
):
    report = tmp_path / "factory-icons.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tests/assert_factory_public_assets.py"),
            "--frontend-root",
            str(ROOT / "app/frontend"),
            "--icons-only",
            "--output",
            str(report),
        ],
        cwd=ROOT,
        env={
            "HOME": str(tmp_path),
            "PATH": os.environ["PATH"],
            "TMPDIR": str(tmp_path),
            "PYTHONPATH": str(ROOT),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(report.read_text())
    assert evidence["precache_count"] == 3
    assert evidence["failures"] == []
    assert len(evidence["protected_controls"]) == 6
    assert evidence["dependency_overrides"] == evidence["route_overlays"] == 0
