"""Phase 4B composition-root and route-registration regression contract."""

from collections import Counter
import inspect

import pytest
from fastapi import FastAPI
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient


FROZEN_OPENAPI_OPERATIONS = {
    ("/health", "get"): "health_check_health_get",
    (
        "/admin/websocket-connections",
        "get",
    ): "get_websocket_connections_admin_websocket_connections_get",
    ("/eventsub", "get"): "eventsub_root_eventsub_get",
    ("/eventsub", "head"): "eventsub_root_eventsub_head",
    ("/eventsub", "post"): "eventsub_callback_eventsub_post",
    ("/api/realtime/events", "get"): "replay_realtime_events_api_realtime_events_get",
}


@pytest.fixture(scope="module")
def app():
    from app.main import app as application

    return application


def _openapi_inventory(application):
    return {
        (path, method): operation["operationId"]
        for path, operations in application.openapi()["paths"].items()
        for method, operation in operations.items()
    }


def _registered_routes(routes):
    """Resolve nested router containers into their effective route contexts."""
    yield from iter_route_contexts(routes)


def test_frozen_inline_openapi_inventory_is_preserved(app):
    inventory = _openapi_inventory(app)
    for operation, endpoint_name in FROZEN_OPENAPI_OPERATIONS.items():
        assert inventory.get(operation) == endpoint_name


def test_no_conflicting_http_method_path_registration(app):
    registrations = [
        (method, route.path)
        for route in _registered_routes(app.routes)
        for method in (route.methods or set())
    ]
    conflicts = [
        registration
        for registration, count in Counter(registrations).items()
        if count > 1
    ]
    assert conflicts == []


def test_websocket_registration_is_preserved(app):
    from app.routes import realtime

    assert any(
        getattr(route, "original_router", None) is realtime.router
        for route in app.routes
    )
    assert any(
        getattr(route, "path", None) == "/ws" for route in realtime.router.routes
    )


def test_extracted_route_modules_do_not_import_main_or_construct_services():
    for module_name in (
        "app.routes.eventsub",
        "app.routes.realtime",
        "app.routes.system",
    ):
        module = __import__(module_name, fromlist=["*"])
        source = inspect.getsource(module)
        assert "from app.main" not in source
        assert "import app.main" not in source
        assert "SessionLocal()" not in source


def test_main_is_a_composition_root_without_inline_route_decorators():
    import app.main as main

    source = inspect.getsource(main)
    assert "@app.get" not in source
    assert "@app.post" not in source
    assert "@app.head" not in source
    assert "@app.websocket" not in source


def test_frontend_spa_and_api_404_order_is_preserved(monkeypatch, tmp_path):
    from app import frontend

    index = tmp_path / "index.html"
    index.write_text("<html>streamvault</html>", encoding="utf-8")
    monkeypatch.setattr(frontend, "_index_html_path", lambda: str(index))

    application = FastAPI()
    application.include_router(frontend.spa_router)
    application.include_router(frontend.catchall_router)

    with TestClient(application) as client:
        assert client.get("/streamers").text == "<html>streamvault</html>"
        assert client.get("/api/missing").status_code == 404


def test_service_worker_compatibility_headers_are_preserved():
    from app import frontend
    from app.middleware_all import install_http_middleware

    application = FastAPI()
    application.include_router(frontend.pwa_router)
    install_http_middleware(application)

    with TestClient(application) as client:
        response = client.get("/registerSW.js")

    assert response.status_code == 200
    assert response.headers["service-worker-allowed"] == "/"
    assert response.headers["cache-control"] == "no-cache"
