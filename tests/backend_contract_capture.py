"""Reproduce the #842 contract from source and an unstarted real application.

Run in an isolated cwd with explicit synthetic test settings. No connection,
provider call, migration or lifespan startup is requested by this capture.
Source inventories are observations, not architecture constraints for refactoring.
"""

from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys


def settings_contract(root: Path) -> dict:
    tree = ast.parse((root / "app/config/settings.py").read_text())
    definition = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    result = {}
    for node in definition.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        name = node.target.id
        value = node.value
        alias = name
        annotation = ast.unparse(node.annotation)
        secret = "SecretStr" in annotation
        default = "<required>" if value is None else ast.unparse(value)
        if isinstance(value, ast.Call) and ast.unparse(value.func) == "Field":
            keywords = {item.arg: item.value for item in value.keywords}
            alias_value = keywords.get("alias")
            if isinstance(alias_value, ast.Constant):
                alias = alias_value.value
            default_value = value.args[0] if value.args else keywords.get("default")
            default = (
                "<required>" if default_value is None else ast.unparse(default_value)
            )
            if "default_factory" in keywords:
                default = "factory: " + ast.unparse(keywords["default_factory"])
        if secret and default not in ("None", "''", '""', "<required>"):
            default = "<secret-default-redacted>"
        result[alias] = {
            "field": name,
            "annotation": annotation,
            "default_source": default,
            "secret": secret,
        }
    return result


def source_inventory(root: Path) -> dict:
    registrations = []
    execution = []
    events = []
    persistence = []
    methods = []
    for path in sorted((root / "app").rglob("*.py")):
        relative = str(path.relative_to(root))
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("send_")
                and "websocket" in relative
            ):
                methods.append({"file": relative, "name": node.name})
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "type"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        events.append(
                            {"file": relative, "line": node.lineno, "type": value.value}
                        )
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            leaf = name.rsplit(".", 1)[-1]
            if leaf in ("register_task_handler", "add_job", "schedule_job"):
                registrations.append(
                    {
                        "file": relative,
                        "line": node.lineno,
                        "call": name,
                        "args_source": [ast.unparse(arg) for arg in node.args],
                        "kwargs_source": {
                            item.arg: ast.unparse(item.value) for item in node.keywords
                        },
                    }
                )
            if leaf in (
                "create_task",
                "ensure_future",
                "create_subprocess_exec",
                "create_subprocess_shell",
                "Popen",
            ):
                execution.append({"file": relative, "line": node.lineno, "call": name})
            if (
                name in ("os.getenv", "os.environ.get")
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                key = node.args[0].value
                if isinstance(key, str) and any(
                    part in key
                    for part in (
                        "DIRECTORY",
                        "BASE_PATH",
                        "BASE_DIR",
                        "LOG_DIR",
                        "KEY_PATH",
                    )
                ):
                    persistence.append(
                        {
                            "file": relative,
                            "line": node.lineno,
                            "env_name": key,
                            "default_source": ast.unparse(node.args[1])
                            if len(node.args) > 1
                            else None,
                        }
                    )
    return {
        "job_and_handler_registrations": registrations,
        "task_and_subprocess_sites": execution,
        "websocket_send_methods": methods,
        "event_type_literals": events,
        "persistent_path_environment": persistence,
    }


def canonical_openapi(schema: dict) -> dict:
    result = deepcopy(schema)
    # FastAPI chooses the ID suffix from an unordered method set on these old routes.
    for path, stem in (
        ("/auth/setup", "setup_page_auth_setup"),
        ("/auth/login", "login_page_auth_login"),
    ):
        operations = result.get("paths", {}).get(path, {})
        if "get" not in operations or "head" not in operations:
            continue
        for method in ("get", "head"):
            operation = operations[method]
            if operation.get("operationId") in (f"{stem}_get", f"{stem}_head"):
                operation["operationId"] = f"{stem}_get"
    return result


def public_contract() -> dict:
    from fastapi.routing import iter_route_contexts
    from app.main import create_app

    application = create_app()
    routes = []
    for context in iter_route_contexts(application.routes):
        route = context.route
        endpoint = getattr(route, "endpoint", None)
        routes.append(
            {
                "path": context.path,
                "methods": sorted(getattr(context, "methods", None) or []),
                "route_class": type(route).__name__,
                "endpoint": f"{endpoint.__module__}.{endpoint.__qualname__}"
                if endpoint
                else None,
            }
        )
    return {
        "openapi": canonical_openapi(application.openapi()),
        "routes_in_registration_order": routes,
        "middleware_in_registration_order": [
            f"{item.cls.__module__}.{item.cls.__qualname__}"
            for item in application.user_middleware
        ],
    }


def capture(root: Path, revision: str) -> dict:
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex, CreateTable
    from app.database import Base
    import app.models  # noqa: F401 - register the canonical metadata

    public = public_contract()
    dialect = postgresql.dialect()
    schema = []
    for table in Base.metadata.sorted_tables:
        schema.append(
            {
                "table": table.name,
                "create_table_postgresql": str(
                    CreateTable(table).compile(dialect=dialect)
                ).strip(),
                "indexes_postgresql": sorted(
                    str(CreateIndex(index).compile(dialect=dialect)).strip()
                    for index in table.indexes
                ),
            }
        )
    return {
        "source_revision": revision,
        "capture_context": "source checkout, synthetic test settings, no lifespan, no frontend dist required; no operator environment values",
        "public": public,
        "settings_names_and_source_defaults": settings_contract(root),
        "source_inventory": source_inventory(root),
        "canonical_postgresql_schema": schema,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    sys.path.insert(0, str(arguments.source_root.resolve()))
    result = capture(arguments.source_root.resolve(), arguments.revision)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "revision": arguments.revision,
                "output": str(arguments.output),
                "routes": len(result["public"]["routes_in_registration_order"]),
                "openapi_paths": len(result["public"]["openapi"]["paths"]),
                "settings": len(result["settings_names_and_source_defaults"]),
                "tables": len(result["canonical_postgresql_schema"]),
            }
        )
    )
