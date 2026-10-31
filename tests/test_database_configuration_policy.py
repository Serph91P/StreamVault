"""#842: URL resolution is explicit configuration, not an imported-test policy."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def resolve(
    tmp_path,
    *,
    database_url=None,
    import_pytest=False,
    test_url=None,
    mode="production",
):
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "PYTHONPATH": str(ROOT),
        "TWITCH_APP_ID": "synthetic",
        "TWITCH_APP_SECRET": "synthetic",
        "BASE_URL": "https://config.example.test",
        "ENVIRONMENT": mode,
    }
    if database_url is not None:
        environment["DATABASE_URL"] = database_url
    if test_url is not None:
        environment["STREAMVAULT_POSTGRES_TEST_URL"] = test_url
    code = (
        ("import pytest\n" if import_pytest else "")
        + """
from app.database import get_database_url, DatabaseLifecycle
from sqlalchemy.engine import make_url
try:
    resolved = get_database_url()
except ValueError as error:
    print(str(error))
    raise SystemExit(42)
assert DatabaseLifecycle().url == resolved
print(make_url(resolved).drivername)
"""
    )
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.parametrize("import_pytest", [False, True])
def test_missing_production_url_never_silently_selects_sqlite(tmp_path, import_pytest):
    result = resolve(tmp_path, import_pytest=import_pytest)
    assert result.returncode == 42, result.stderr + result.stdout
    assert "DATABASE_URL" in result.stdout
    assert "not set" in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("import_pytest", [False, True])
def test_explicit_postgres_is_not_replaced_by_test_import_or_test_url(
    tmp_path, import_pytest
):
    result = resolve(
        tmp_path,
        database_url="postgresql://localhost/synthetic",
        import_pytest=import_pytest,
        test_url="sqlite:///:memory:",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "postgresql"


@pytest.mark.parametrize("url", ["sqlite:///:memory:", "sqlite:///production.db"])
def test_production_configuration_cannot_select_sqlite(tmp_path, url):
    result = resolve(tmp_path, database_url=url)
    assert result.returncode == 42, result.stderr + result.stdout
    assert "PostgreSQL" in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_sqlite_requires_explicit_configuration_or_lifecycle_injection(tmp_path):
    result = resolve(tmp_path, database_url="sqlite:///:memory:", mode="test")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "sqlite"
    from app.database import DatabaseLifecycle

    lifecycle = DatabaseLifecycle("sqlite:///:memory:")
    assert lifecycle.url == "sqlite:///:memory:"
    assert lifecycle._sync_engine is None
    assert lifecycle._async_engine is None
