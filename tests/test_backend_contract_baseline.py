"""#842 baseline: preserve public interfaces, not the old internal module layout."""

import copy
import json
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.database import Base
from tests.backend_contract_capture import public_contract, settings_contract

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((ROOT / "docs/architecture/contracts/base-842.json").read_text())
DEVELOP_1045 = json.loads(
    (ROOT / "tests/fixtures/accepted-develop-1045.json").read_text()
)


def test_public_openapi_routes_and_middleware_preserve_verified_base():
    current = public_contract()
    expected = BASELINE["public"]
    # #938 intentionally replaces destructive no-body cleanup with optional preview/
    # confirmation. Verify that exact additive contract before comparing the rest.
    from app.services.system.temporary_cleanup_service import TemporaryCleanupRequest

    schema = copy.deepcopy(current["openapi"])
    operation = schema["paths"]["/api/admin/maintenance/cleanup-temp"]["post"]
    baseline_operation = expected["openapi"]["paths"][
        "/api/admin/maintenance/cleanup-temp"
    ]["post"]
    assert operation.pop("requestBody") == {
        "content": {
            "application/json": {
                "schema": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/TemporaryCleanupRequest"},
                        {"type": "null"},
                    ],
                    "title": "Request",
                }
            }
        }
    }
    assert (
        operation["description"]
        == "Preview expired, unowned temporary files; delete only confirmed identities."
    )
    operation["description"] = baseline_operation["description"]
    if "422" not in baseline_operation["responses"]:
        assert operation["responses"].pop("422") == {
            "description": "Validation Error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                }
            },
        }
    cleanup_schemas = json.loads(
        (ROOT / "docs/architecture/contracts/cleanup-938.json").read_text()
    )
    for name, definition in cleanup_schemas.items():
        assert schema["components"]["schemas"].pop(name) == definition
    defaults = TemporaryCleanupRequest()
    assert (
        defaults.dry_run is True
        and defaults.confirmed is False
        and defaults.candidates == []
    )
    # Reuse reviewed PR969's exact additive generation query contract; the frozen
    # pre-modernization snapshot remains unchanged for every other field.
    realtime_parameters = schema["paths"]["/api/realtime/events"]["get"]["parameters"]
    assert realtime_parameters.pop() == {
        "name": "generation",
        "in": "query",
        "required": False,
        "schema": {
            "anyOf": [{"type": "string", "maxLength": 36}, {"type": "null"}],
            "title": "Generation",
        },
    }
    # #933 adds only this codec field and these four SPA entrypoints.
    assert schema["components"]["schemas"]["RecordingSettingsSchema"]["properties"].pop(
        "supported_codecs"
    ) == {
        "type": "string",
        "pattern": "^(?:h264|h265|av1)(?:,(?:h264|h265|av1))*$",
        "title": "Supported Codecs",
        "description": "Global recording codec preferences (ordered h264, h265, av1 list)",
        "default": "h264,h265",
    }
    spa_paths = ("/onboarding", "/system", "/overview", "/activity")
    for path in spa_paths:
        operation = copy.deepcopy(expected["openapi"]["paths"]["/streamers"])
        operation["get"]["operationId"] = f"serve_spa_routes_{path[1:]}_get"
        assert schema["paths"].pop(path) == operation
    # Exact published #1045 additions; never regenerate the historical baseline.
    for path, definition in DEVELOP_1045["added_paths"].items():
        assert schema["paths"].pop(path) == definition
    for path, definition in DEVELOP_1045["added_heads"].items():
        assert schema["paths"][path].pop("head") == definition
    # Owner-confirmed #842 health split adds exactly one GET, not a new API family.
    assert schema["paths"].pop("/api/health/startup") == {
        "get": {
            "tags": ["health"],
            "summary": "Startup Check",
            "operationId": "startup_check_api_health_startup_get",
            "responses": {
                "200": {
                    "description": "Successful Response",
                    "content": {"application/json": {"schema": {}}},
                }
            },
        }
    }
    readiness = schema["paths"]["/api/health/ready"]["get"]
    assert (
        readiness["description"]
        == "Require owned lifecycle integrity plus the configured DB/tool policy."
    )
    readiness["description"] = expected["openapi"]["paths"]["/api/health/ready"]["get"][
        "description"
    ]
    assert schema == expected["openapi"]

    # Handler modules may move; registration order, route kind and methods may not.
    def signatures(routes):
        return [
            (route["path"], route["methods"], route["route_class"]) for route in routes
        ]

    expected_routes = signatures(expected["routes_in_registration_order"])
    insertion = expected_routes.index(("/streamers", ["GET"], "APIRoute")) + 1
    expected_routes[insertion:insertion] = [
        (path, ["GET"], "APIRoute") for path in spa_paths
    ]
    insertion = expected_routes.index(("/api/videos", ["GET"], "APIRoute"))
    expected_routes[insertion:insertion] = [
        (path, ["GET"], "APIRoute") for path in DEVELOP_1045["added_paths"]
    ]
    for path in DEVELOP_1045["added_heads"]:
        insertion = expected_routes.index((path, ["GET"], "APIRoute")) + 1
        expected_routes.insert(insertion, (path, ["HEAD"], "APIRoute"))
    insertion = expected_routes.index(("/api/health/live", ["GET"], "APIRoute"))
    expected_routes.insert(insertion, ("/api/health/startup", ["GET"], "APIRoute"))
    assert signatures(current["routes_in_registration_order"]) == expected_routes
    assert (
        current["middleware_in_registration_order"]
        == expected["middleware_in_registration_order"]
    )


def test_capture_canonicalizes_only_known_dual_method_operation_id_nondeterminism():
    from tests.backend_contract_capture import canonical_openapi

    schema = {
        "paths": {
            "/auth/setup": {
                "get": {"operationId": "setup_page_auth_setup_head"},
                "head": {"operationId": "setup_page_auth_setup_head"},
            },
            "/auth/login": {
                "get": {"operationId": "changed_login_handler_head"},
                "head": {"operationId": "changed_login_handler_head"},
            },
            "/other": {"get": {"operationId": "other_head"}},
        }
    }
    original = copy.deepcopy(schema)
    result = canonical_openapi(schema)
    assert schema == original
    assert result["paths"]["/auth/setup"] == {
        "get": {"operationId": "setup_page_auth_setup_get"},
        "head": {"operationId": "setup_page_auth_setup_get"},
    }
    assert result["paths"]["/auth/login"] == original["paths"]["/auth/login"]
    assert result["paths"]["/other"] == original["paths"]["/other"]


def test_environment_names_and_static_defaults_preserve_verified_base():
    assert settings_contract(ROOT) == BASELINE["settings_names_and_source_defaults"]


def test_feature_model_layout_preserves_canonical_postgresql_schema():
    dialect = postgresql.dialect()
    current = [
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
        for table in Base.metadata.sorted_tables
    ]
    added_tables = {
        entry["table"] for entry in DEVELOP_1045["canonical_postgresql_schema"]
    }
    assert [
        entry for entry in current if entry["table"] in added_tables
    ] == DEVELOP_1045["canonical_postgresql_schema"]
    assert [
        entry for entry in current if entry["table"] not in added_tables
    ] == BASELINE["canonical_postgresql_schema"]
