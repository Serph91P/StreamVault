"""Exact new dependency targets from #1079–#1087; build tools are not runtime deps."""

from importlib.metadata import version
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_AND_TOOL_TARGETS = {
    "pytest-cov": "7.1.0",
    "fastapi": "0.163.1",
    "psycopg": "3.3.9",
    "psycopg-binary": "3.3.9",
    "pydantic-settings": "2.16.3",
    "ruff": "0.17.5",
    "pytest-asyncio": "1.5.0",
    "annotated-doc": "0.0.6",
    "argon2-cffi-bindings": "26.2.0",
    "apprise": "2.2.0",
    "cachetools": "8.0.0",
    "mypy": "2.4.1",
    "multidict": "7.2.1",
    "pycryptodome": "4.5.0",
}
BUILD_TARGETS = {"setuptools": "84.2.1", "setuptools-scm": "10.3.4"}


@pytest.mark.parametrize("name,expected", RUNTIME_AND_TOOL_TARGETS.items())
def test_new_target_is_locked_and_actually_installed(name: str, expected: str) -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    locked = {package["name"]: package.get("version") for package in lock["package"]}
    assert locked[name] == expected
    assert version(name) == expected


def test_build_targets_remain_isolated_from_runtime_lock() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert project["build-system"]["requires"] == [
        f"{name}=={expected}" for name, expected in BUILD_TARGETS.items()
    ]
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    assert not BUILD_TARGETS.keys() & {package["name"] for package in lock["package"]}
    assert len(RUNTIME_AND_TOOL_TARGETS | BUILD_TARGETS) == 16
