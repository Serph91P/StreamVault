"""P0 contract freeze: compare the public/backend topology to the frozen base."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SNAPSHOT = ROOT / "tests/fixtures/backend_contract_snapshot.json"


def _source(path: str) -> ast.Module:
    return ast.parse((ROOT / path).read_text(encoding="utf-8"))


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _literal_or_marker(node: ast.AST | None) -> str | int | float | bool | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    return (
        f"<{_call_name(node.func) or type(node).__name__}>"
        if isinstance(node, ast.Call)
        else f"<{type(node).__name__}>"
    )


def _settings_contract() -> dict[str, object]:
    settings = next(
        node
        for node in _source("app/config/settings.py").body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    return {
        field.target.id: _literal_or_marker(field.value)
        for field in settings.body
        if isinstance(field, ast.AnnAssign) and isinstance(field.target, ast.Name)
    }


def _main_contract() -> dict[str, list[str]]:
    tree = _source("app/main.py")
    includes: list[str] = []
    middleware: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "include_router" and node.args:
            includes.append(ast.unparse(node.args[0]))
        if node.func.attr == "add_middleware" and node.args:
            middleware.append(ast.unparse(node.args[0]))
        if node.func.attr == "install_http_middleware":
            middleware.append("install_http_middleware")
    return {"routers": includes, "middleware": middleware}


def _websocket_event_methods() -> list[str]:
    manager = next(
        node
        for node in _source("app/services/communication/websocket_manager.py").body
        if isinstance(node, ast.ClassDef) and node.name == "ConnectionManager"
    )
    return sorted(
        node.name
        for node in manager.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("send_")
    )


def _service_job_process_contract() -> dict[str, object]:
    services = sorted(
        str(path.relative_to(ROOT)) for path in (ROOT / "app/services").rglob("*.py")
    )
    jobs: list[str] = []
    processes: dict[str, list[str]] = {}
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = sorted(
            {
                name
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and (name := _call_name(node.func))
                in {
                    "asyncio.create_subprocess_exec",
                    "subprocess.run",
                    "subprocess.Popen",
                }
            }
        )
        if calls:
            processes[str(path.relative_to(ROOT))] = calls
        if path.relative_to(ROOT).as_posix() == "app/lifespan.py":
            jobs = sorted(
                {
                    ast.unparse(node.args[0])
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and _call_name(node.func) == "asyncio.create_task"
                    and node.args
                }
            )
    return {
        "service_modules": services,
        "lifespan_jobs": jobs,
        "subprocess_kinds": processes,
    }


def _openapi_contract() -> list[str]:
    """Freeze public OpenAPI path/method shape, not FastAPI's unstable IDs.

    Several legacy routes answer both GET and HEAD. FastAPI derives their
    generated operation IDs from a set, so IDs vary between interpreter runs;
    the externally relevant path/method surface does not.
    """
    try:
        from app.main import app
    except Exception as error:  # pragma: no cover - reports a real bootstrap failure
        pytest.fail(f"cannot derive OpenAPI contract: {error}")
    return sorted(
        f"{method.upper()} {path}"
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    )


def collect_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "openapi_operations": _openapi_contract(),
        "route_and_middleware_order": _main_contract(),
        "websocket_event_methods": _websocket_event_methods(),
        "environment_defaults": _settings_contract(),
        "services_jobs_and_subprocesses": _service_job_process_contract(),
        "persistent_paths": {
            "recording_directory": "/recordings",
            "artwork_base_path": "/recordings/.artwork",
            "media_path": "/recordings/.media",
            "logs_default": "/app/logs",
            "live_output_default": "/tmp/streamvault-live",
        },
    }


def test_backend_contract_snapshot_matches_frozen_base():
    """Any API/topology change must be reviewed as an intentional contract delta."""
    assert SNAPSHOT.exists(), (
        "Generate and review the P0 snapshot before changing contracts."
    )
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert collect_contract() == expected


if __name__ == "__main__":
    import sys

    rendered = json.dumps(collect_contract(), indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
