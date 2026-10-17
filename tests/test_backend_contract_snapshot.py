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


def _literal_or_marker(node: ast.AST | None) -> object:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_literal_or_marker(item) for item in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _literal_or_marker(key): _literal_or_marker(value)
            for key, value in zip(node.keys, node.values, strict=True)
        }
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
    contract: dict[str, object] = {}
    for field in settings.body:
        if not isinstance(field, ast.AnnAssign) or not isinstance(
            field.target, ast.Name
        ):
            continue
        field_name = field.target.id
        annotation = ast.unparse(field.annotation)
        secret = "SecretStr" in annotation
        alias = field_name
        value = field.value
        default_factory: ast.AST | None = None
        if isinstance(value, ast.Call) and _call_name(value.func) == "Field":
            keywords = {
                keyword.arg: keyword.value for keyword in value.keywords if keyword.arg
            }
            alias_value = keywords.get("alias")
            if isinstance(alias_value, ast.Constant) and isinstance(
                alias_value.value, str
            ):
                alias = alias_value.value
            value = keywords.get("default")
            default_factory = keywords.get("default_factory")
        entry: dict[str, object] = {"field": field_name, "secret": secret}
        if default_factory is not None:
            factory_value = (
                default_factory.body
                if isinstance(default_factory, ast.Lambda)
                else default_factory
            )
            entry["default_factory"] = _literal_or_marker(factory_value)
        else:
            entry["default"] = _literal_or_marker(value)
        contract[alias] = entry
    return contract


def _main_contract() -> dict[str, list[str]]:
    tree = _source("app/main.py")
    includes: list[str] = []
    middleware: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "install_http_middleware"
        ):
            middleware.append("install_http_middleware")
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "include_router" and node.args:
            includes.append(ast.unparse(node.args[0]))
        if node.func.attr == "add_middleware" and node.args:
            middleware.append(ast.unparse(node.args[0]))
        if node.func.attr == "install_http_middleware":
            middleware.append("install_http_middleware")
    return {"routers": includes, "middleware": middleware}


def _fallback_string(path: str, target: str) -> str:
    for node in ast.walk(_source(path)):
        if not isinstance(node, ast.Assign) or not any(
            (isinstance(item, ast.Name) and item.id == target)
            or (isinstance(item, ast.Attribute) and item.attr == target)
            for item in node.targets
        ):
            continue
        strings = [
            item.value
            for item in ast.walk(node.value)
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        if strings:
            return strings[-1]
    raise AssertionError(f"cannot derive persistent default for {path}:{target}")


def _persistent_paths_contract() -> dict[str, str]:
    settings = _settings_contract()
    return {
        "recording_directory": settings["RECORDING_DIRECTORY"]["default"],  # type: ignore[index,return-value]
        "artwork_base_path": settings["ARTWORK_BASE_PATH"]["default"],  # type: ignore[index,return-value]
        "logs_default": _fallback_string("app/config/logging_config.py", "logs_base"),
        "live_output_default": _fallback_string(
            "app/services/live_streaming_service.py", "_output_root"
        ),
    }


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


def _openapi_contract() -> list[dict[str, object]]:
    """Freeze public OpenAPI path/method shape, not FastAPI's unstable IDs.

    Several legacy routes answer both GET and HEAD. FastAPI derives their
    generated operation IDs from a set, so IDs vary between interpreter runs;
    the externally relevant path/method surface does not.
    """
    try:
        from app.main import app
    except Exception as error:  # pragma: no cover - reports a real bootstrap failure
        pytest.fail(f"cannot derive OpenAPI contract: {error}")
    operations: list[dict[str, object]] = []
    for path, path_item in app.openapi()["paths"].items():
        for method, operation in path_item.items():
            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            }:
                continue
            responses = {
                status: {
                    key: value
                    for key, value in response.items()
                    if key in {"content", "headers"}
                }
                for status, response in sorted(operation.get("responses", {}).items())
            }
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "request_body": operation.get("requestBody"),
                    "responses": responses,
                    "security": operation.get("security", []),
                }
            )
    return sorted(
        operations, key=lambda operation: (operation["method"], operation["path"])
    )


def collect_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "openapi_operations": _openapi_contract(),
        "route_and_middleware_order": _main_contract(),
        "websocket_event_methods": _websocket_event_methods(),
        "environment_defaults": _settings_contract(),
        "services_jobs_and_subprocesses": _service_job_process_contract(),
        "persistent_paths": _persistent_paths_contract(),
    }


def test_backend_contract_snapshot_matches_frozen_base():
    """Any API/topology change must be reviewed as an intentional contract delta."""
    assert SNAPSHOT.exists(), (
        "Generate and review the P0 snapshot before changing contracts."
    )
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert collect_contract() == expected


def test_settings_contract_preserves_external_aliases_and_safe_default_factories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """P0 freezes deployment names without reading or constructing settings."""
    settings_path = tmp_path / "app/config/settings.py"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(
        """
class Settings:
    auth_jwt_secret: SecretStr | None = Field(default=None, alias="AUTH_JWT_SECRET")
    CORS_ALLOW_METHODS: list[str] = Field(default_factory=lambda: ["GET", "POST"])
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)

    assert _settings_contract() == {
        "AUTH_JWT_SECRET": {
            "default": None,
            "field": "auth_jwt_secret",
            "secret": True,
        },
        "CORS_ALLOW_METHODS": {
            "default_factory": ["GET", "POST"],
            "field": "CORS_ALLOW_METHODS",
            "secret": False,
        },
    }


def test_main_contract_includes_direct_http_middleware_installation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    main_path = tmp_path / "app/main.py"
    main_path.parent.mkdir(parents=True)
    main_path.write_text(
        """
def configure(application):
    application.include_router(api)
    install_http_middleware(application)
    application.add_middleware(AuthMiddleware)
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)

    assert _main_contract() == {
        "middleware": ["install_http_middleware", "AuthMiddleware"],
        "routers": ["api"],
    }


def test_persistent_paths_are_derived_from_their_source_definitions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    config_path = tmp_path / "app/config/settings.py"
    logging_path = tmp_path / "app/config/logging_config.py"
    live_path = tmp_path / "app/services/live_streaming_service.py"
    for path in (config_path, logging_path, live_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
class Settings:
    RECORDING_DIRECTORY: str = "/contract-recordings"
    ARTWORK_BASE_PATH: str = "/contract-recordings/.artwork"
""",
        encoding="utf-8",
    )
    logging_path.write_text(
        'logs_base = settings.LOGS_BASE_DIR or "/contract-logs"\n', encoding="utf-8"
    )
    live_path.write_text(
        'self._output_root = Path(output_root or "/contract-live")\n', encoding="utf-8"
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)

    assert _persistent_paths_contract() == {
        "artwork_base_path": "/contract-recordings/.artwork",
        "live_output_default": "/contract-live",
        "logs_default": "/contract-logs",
        "recording_directory": "/contract-recordings",
    }


def test_openapi_contract_freezes_request_response_and_security_shape(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeApp:
        def openapi(self) -> dict[str, object]:
            return {
                "paths": {
                    "/widgets": {
                        "post": {
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {"schema": {"type": "object"}}
                                },
                            },
                            "responses": {
                                "201": {
                                    "description": "created",
                                    "content": {
                                        "application/json": {
                                            "schema": {"type": "string"}
                                        }
                                    },
                                },
                                "422": {"description": "invalid"},
                            },
                            "security": [{"ApiKeyAuth": []}],
                        }
                    }
                }
            }

    import types

    monkeypatch.setitem(sys.modules, "app.main", types.SimpleNamespace(app=FakeApp()))
    assert _openapi_contract() == [
        {
            "method": "POST",
            "path": "/widgets",
            "request_body": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "201": {
                    "content": {"application/json": {"schema": {"type": "string"}}}
                },
                "422": {},
            },
            "security": [{"ApiKeyAuth": []}],
        }
    ]


if __name__ == "__main__":
    import sys

    rendered = json.dumps(collect_contract(), indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
