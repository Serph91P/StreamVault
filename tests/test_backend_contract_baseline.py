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


def test_public_openapi_routes_and_middleware_preserve_verified_base():
    current = public_contract()
    expected = BASELINE["public"]
    assert current["openapi"] == expected["openapi"]

    # Handler modules may move; registration order, route kind and methods may not.
    def signatures(routes):
        return [
            (route["path"], route["methods"], route["route_class"]) for route in routes
        ]

    assert signatures(current["routes_in_registration_order"]) == signatures(
        expected["routes_in_registration_order"]
    )
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
    assert current == BASELINE["canonical_postgresql_schema"]
