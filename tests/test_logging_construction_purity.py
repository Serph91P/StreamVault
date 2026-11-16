"""Logger lookup must not bootstrap configuration or filesystem resources."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_compatibility_entrypoint_delegates_composition_to_the_factory():
    from app.main import app, create_app

    assert create_app.__module__ == "app.bootstrap.application"
    assert create_app() is app


@pytest.mark.parametrize("configured", [False, True])
def test_default_logger_lookup_has_no_configuration_or_filesystem_side_effects(
    tmp_path, configured
):
    # Probe a fresh application interpreter, not pytest/coverage startup hooks.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "TMPDIR": str(tmp_path),
        "PYTHONPATH": str(ROOT),
        "PYTHONDONTWRITEBYTECODE": "1",
        "LOGS_BASE_DIR": str(tmp_path / "logs"),
    }
    if configured:
        env.update(
            TWITCH_APP_ID="synthetic",
            TWITCH_APP_SECRET="synthetic",
            BASE_URL="http://localhost:8000",
        )
    program = """
import logging
import pathlib
import sys

def forbidden(*args, **kwargs):
    raise AssertionError("logger lookup must not create directories")
pathlib.Path.mkdir = forbidden
from app.config.logging_config import setup_logging
logger = setup_logging()
assert logger is logging.getLogger("streamvault")
assert not logger.handlers
assert "app.config.settings" not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "logs").exists()
