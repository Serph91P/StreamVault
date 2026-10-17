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


def _factory_contract(node: ast.AST) -> object:
    """Render a factory's source form without evaluating it."""
    if isinstance(node, ast.Name):
        return {"call": node.id, "kind": "name"}
    if isinstance(node, ast.Lambda):
        return _literal_or_marker(node.body)
    return {"expression": ast.unparse(node)}


def _settings_class() -> ast.ClassDef:
    return next(
        node
        for node in _source("app/config/settings.py").body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )


def _settings_contract() -> dict[str, object]:
    settings = _settings_class()
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
        has_default = value is not None
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
            if value.args:
                value = value.args[0]
                has_default = True
            else:
                value = keywords.get("default")
                has_default = "default" in keywords
            default_factory = keywords.get("default_factory")
        entry: dict[str, object] = {"field": field_name, "secret": secret}
        if default_factory is not None:
            entry["default_factory"] = _factory_contract(default_factory)
        else:
            entry["default"] = (
                {"required": True} if not has_default else _literal_or_marker(value)
            )
        contract[alias] = entry
    return contract


def _settings_property_aliases() -> dict[str, str]:
    """Freeze public compatibility accessors without calling them or Settings."""
    aliases: dict[str, str] = {}
    for node in _settings_class().body:
        if not isinstance(node, ast.FunctionDef) or not node.name.isupper():
            continue
        if not any(
            isinstance(decorator, ast.Name) and decorator.id == "property"
            for decorator in node.decorator_list
        ):
            continue
        targets = sorted(
            {
                expression.attr
                for expression in ast.walk(node)
                if isinstance(expression, ast.Attribute)
                and isinstance(expression.value, ast.Name)
                and expression.value.id == "self"
            }
        )
        if targets:
            aliases[node.name] = ",".join(targets)
    return aliases


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


def _persistent_paths_contract() -> dict[str, object]:
    settings = _settings_contract()
    frontend = _source("app/frontend.py")
    recording_root = next(
        ast.unparse(node.value).removeprefix("settings.")
        for node in ast.walk(frontend)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "recordings_dir"
            for target in node.targets
        )
    )
    media_expression = next(
        node.value
        for node in ast.walk(frontend)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "images_dir"
            for target in node.targets
        )
        and isinstance(node.value, ast.BinOp)
        and isinstance(node.value.op, ast.Div)
        and isinstance(node.value.right, ast.Constant)
        and isinstance(node.value.right.value, str)
    )
    if not (
        isinstance(media_expression.left, ast.Call)
        and _call_name(media_expression.left.func) == "Path"
        and len(media_expression.left.args) == 1
        and isinstance(media_expression.left.args[0], ast.Name)
        and media_expression.left.args[0].id == "recordings_dir"
    ):
        raise AssertionError("media path must derive from recordings_dir")
    media_suffix = _literal_or_marker(media_expression.right)
    return {
        "recording_directory": settings["RECORDING_DIRECTORY"]["default"],  # type: ignore[index,return-value]
        "artwork_base_path": settings["ARTWORK_BASE_PATH"]["default"],  # type: ignore[index,return-value]
        "logs_default": _fallback_string("app/config/logging_config.py", "logs_base"),
        "live_output_default": _fallback_string(
            "app/services/live_streaming_service.py", "_output_root"
        ),
        "media_path": {"recording_root": recording_root, "suffix": media_suffix},
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


def _openapi_contract() -> dict[str, object]:
    """Freeze public operations plus reachable schema and security definitions.

    Generated operation IDs are intentionally omitted: FastAPI derives them
    nondeterministically for legacy GET/HEAD pairs.  Request parameters,
    effective security and reachable component definitions are public contracts.
    """
    try:
        from app.main import app
    except Exception as error:  # pragma: no cover - reports a real bootstrap failure
        pytest.fail(f"cannot derive OpenAPI contract: {error}")
    document = app.openapi()
    components = document.get("components", {})
    schemas = components.get("schemas", {})
    security_schemes = components.get("securitySchemes", {})
    referenced_schemas: set[str] = set()

    def remember_schema_refs(value: object) -> None:
        if isinstance(value, dict):
            reference = value.get("$ref")
            if isinstance(reference, str) and reference.startswith(
                "#/components/schemas/"
            ):
                name = reference.rsplit("/", 1)[-1]
                if name not in referenced_schemas:
                    referenced_schemas.add(name)
                    remember_schema_refs(schemas.get(name, {}))
            for child in value.values():
                remember_schema_refs(child)
        elif isinstance(value, list):
            for child in value:
                remember_schema_refs(child)

    referenced_security: set[str] = set()
    operations: list[dict[str, object]] = []
    for path, path_item in document["paths"].items():
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
            parameters = [
                *path_item.get("parameters", []),
                *operation.get("parameters", []),
            ]
            security = operation.get("security", document.get("security", []))
            remember_schema_refs(
                {
                    "parameters": parameters,
                    "request": operation.get("requestBody"),
                    "responses": responses,
                }
            )
            for requirement in security:
                referenced_security.update(requirement)
            operations.append(
                {
                    "method": method.upper(),
                    "path": path,
                    "parameters": parameters,
                    "request_body": operation.get("requestBody"),
                    "responses": responses,
                    "security": security,
                }
            )
    return {
        "operations": sorted(
            operations, key=lambda operation: (operation["method"], operation["path"])
        ),
        "components": {
            "schemas": {name: schemas[name] for name in sorted(referenced_schemas)},
            "security_schemes": {
                name: security_schemes[name] for name in sorted(referenced_security)
            },
        },
    }


def collect_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "openapi_operations": _openapi_contract(),
        "route_and_middleware_order": _main_contract(),
        "websocket_event_methods": _websocket_event_methods(),
        "environment_defaults": _settings_contract(),
        "settings_property_aliases": _settings_property_aliases(),
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
    twitch_app_secret: SecretStr = Field(alias="TWITCH_APP_SECRET")
    positionally_optional: SecretStr | None = Field(None, alias="POSITIONAL_OPTIONAL")
    APPRISE_URLS: list[str] = Field(default_factory=list)
    CORS_ALLOW_METHODS: list[str] = Field(default_factory=lambda: ["GET", "POST"])

    @property
    def AUTH_JWT_SECRET(self) -> str:
        return _secret_value(self.auth_jwt_secret) or ""
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
        "APPRISE_URLS": {
            "default_factory": {"call": "list", "kind": "name"},
            "field": "APPRISE_URLS",
            "secret": False,
        },
        "TWITCH_APP_SECRET": {
            "default": {"required": True},
            "field": "twitch_app_secret",
            "secret": True,
        },
        "POSITIONAL_OPTIONAL": {
            "default": None,
            "field": "positionally_optional",
            "secret": True,
        },
    }
    assert _settings_property_aliases() == {
        "AUTH_JWT_SECRET": "auth_jwt_secret",
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
    frontend_path = tmp_path / "app/frontend.py"
    for path in (config_path, logging_path, live_path, frontend_path):
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
    frontend_path.write_text(
        """
recordings_dir = settings.RECORDING_DIRECTORY
images_dir = Path(recordings_dir) / ".contract-media"
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)

    assert _persistent_paths_contract() == {
        "artwork_base_path": "/contract-recordings/.artwork",
        "live_output_default": "/contract-live",
        "logs_default": "/contract-logs",
        "media_path": {
            "recording_root": "RECORDING_DIRECTORY",
            "suffix": ".contract-media",
        },
        "recording_directory": "/contract-recordings",
    }

    frontend_path.write_text(
        "recordings_dir = settings.RECORDING_DIRECTORY\n"
        'images_dir = Path("/contract-other-root") / ".contract-media"\n',
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="media path"):
        _persistent_paths_contract()


def test_openapi_contract_freezes_request_response_and_security_shape(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeApp:
        def openapi(self) -> dict[str, object]:
            return {
                "paths": {
                    "/widgets": {
                        "parameters": [
                            {"name": "tenant", "in": "header", "required": True}
                        ],
                        "post": {
                            "parameters": [
                                {"name": "since", "in": "query", "required": True}
                            ],
                            "requestBody": {
                                "required": True,
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/Widget"
                                        }
                                    }
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
                        },
                    }
                },
                "security": [{"GlobalAuth": []}],
                "components": {
                    "schemas": {
                        "Widget": {
                            "type": "object",
                            "required": ["id"],
                            "properties": {"id": {"type": "integer"}},
                        }
                    },
                    "securitySchemes": {
                        "ApiKeyAuth": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "X-Api-Key",
                        },
                        "GlobalAuth": {"type": "http", "scheme": "bearer"},
                    },
                },
            }

    import types

    monkeypatch.setitem(sys.modules, "app.main", types.SimpleNamespace(app=FakeApp()))
    assert _openapi_contract() == {
        "operations": [
            {
                "method": "POST",
                "path": "/widgets",
                "parameters": [
                    {"name": "tenant", "in": "header", "required": True},
                    {"name": "since", "in": "query", "required": True},
                ],
                "request_body": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Widget"}
                        }
                    },
                },
                "responses": {
                    "201": {
                        "content": {"application/json": {"schema": {"type": "string"}}}
                    },
                    "422": {},
                },
                "security": [{"ApiKeyAuth": []}],
            }
        ],
        "components": {
            "schemas": {
                "Widget": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "integer"}},
                }
            },
            "security_schemes": {
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-Api-Key"},
            },
        },
    }


if __name__ == "__main__":
    import sys

    rendered = json.dumps(collect_contract(), indent=2, sort_keys=True) + "\n"
    if "--write" in sys.argv:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
