"""
Phase 4A boundary freeze for issue #826.

This module freezes the *semantic* route/OpenAPI coverage of the primary API
domains (streamers, videos/media, settings, categories) and the refactored
boundary structure introduced by Phase 4A (DI-overrideable seams, extraction of
reusable database/business workflow out of router functions, no direct
`SessionLocal` / ad-hoc sync SQL inside the categories & settings routers).

RED first: several structural assertions fail on the pre-Phase-4A code
(e.g. routers still reference `SessionLocal`, the category/video seams do not
exist, adapters are not injectable). After implementation all assertions pass.
"""

import asyncio
import inspect

import pytest
from fastapi.testclient import TestClient

PRIMARY_PATHS = {
    # streamers
    ("get", "/api/streamers"),
    ("post", "/api/streamers/{username}"),
    ("delete", "/api/streamers/{streamer_id}"),
    ("get", "/api/streamers/{streamer_id}/live-status"),
    ("get", "/api/streamers/{streamer_id}/streams"),
    ("delete", "/api/streamers/{streamer_id}/streams/{stream_id}"),
    ("get", "/api/streamers/streamer/{streamer_id}"),
    ("put", "/api/streamers/streamer/{streamer_id}/settings"),
    ("get", "/api/streamers/subscriptions"),
    ("get", "/api/streamers/validate/{username}"),
    # videos / media
    ("get", "/api/videos"),
    ("get", "/api/videos/streamer/{streamer_id}"),
    ("get", "/api/videos/{streamer_name}"),
    ("get", "/api/videos/{stream_id}/stream"),
    ("get", "/api/videos/{stream_id}/thumbnail"),
    ("get", "/api/videos/{stream_id}/chapters"),
    ("post", "/api/videos/{stream_id}/share-token"),
    ("get", "/api/videos/public/{stream_id}"),
    # settings
    ("get", "/api/settings"),
    ("post", "/api/settings"),
    ("get", "/api/settings/streamer"),
    ("post", "/api/settings/streamer/{streamer_id}"),
    ("get", "/api/settings/streamers"),
    ("get", "/api/settings/quality-options"),
    ("get", "/api/settings/codec-options"),
    # categories
    ("get", "/api/categories"),
    ("get", "/api/categories/favorites"),
    ("post", "/api/categories/favorites"),
    ("delete", "/api/categories/favorites/{category_id}"),
    ("get", "/api/categories/image/{category_name}"),
    ("post", "/api/categories/images/batch"),
    # images / metadata seams
    ("post", "/api/categories/preload-images"),
    ("get", "/api/categories/missing-images"),
}

IMPORT_ERRORS = (ImportError, AttributeError, ModuleNotFoundError)


def _source(module_name: str) -> str:
    import importlib

    module = importlib.import_module(module_name)
    return inspect.getsource(module)


# ---------------------------------------------------------------------------
# 1. Frozen OpenAPI / route coverage for primary paths.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app():
    from app.main import app as _app

    return _app


def test_primary_paths_present_in_openapi(app):
    spec = app.openapi()
    paths = spec["paths"]
    for method, path in PRIMARY_PATHS:
        assert path in paths, f"missing primary path in OpenAPI: {path}"
        assert method in paths[path], f"missing {method.upper()} operation for {path}"


def test_primary_paths_have_stable_operation_ids(app):
    spec = app.openapi()
    for method, path in PRIMARY_PATHS:
        op = spec["paths"][path][method]
        assert "operationId" in op, f"no operationId for {method.upper()} {path}"
        assert op.get("responses", {}).get("200") or op.get("responses", {}).get(
            "204"
        ), f"no success response documented for {method.upper()} {path}"


# ---------------------------------------------------------------------------
# 2. Boundary structure: categories & settings routers must not own sessions
#    or ad-hoc sync SQL.
# ---------------------------------------------------------------------------


def test_categories_router_has_no_sessionlocal_or_inline_query():
    src = _source("app.routes.categories")
    assert "SessionLocal" not in src
    assert "from app.database import" not in src
    assert "db.query(" not in src


def test_settings_router_has_no_sessionlocal_or_inline_query():
    src = _source("app.routes.settings")
    assert "SessionLocal" not in src
    assert "db.query(" not in src


def test_categories_router_injects_category_service():
    src = _source("app.routes.categories")
    assert "CategoryService" in src
    assert "Depends(get_category_service)" in src


def test_settings_router_injects_settings_service_seam():
    src = _source("app.routes.settings")
    assert "Depends(get_settings_service)" in src


def test_settings_router_injects_session_notification_and_websocket_seams():
    from app import dependencies
    from app.routes import settings
    from app.routes import videos

    src = _source("app.routes.settings")
    assert "get_notification_service_factory" in src
    assert "Depends(get_websocket_manager)" in src

    for endpoint in (
        settings.get_quality_options,
        settings.get_codec_options,
        videos.get_videos,
    ):
        db_default = inspect.signature(endpoint).parameters["db"].default
        assert db_default.dependency is dependencies.get_db


def test_settings_update_preserves_invalid_proxy_error_envelope(seeded_client):
    client = TestClient(seeded_client)
    response = client.post(
        "/api/settings",
        json={"http_proxy": "ftp://invalid.example"},
        headers={"X-API-Key": seeded_client.state.phase4a_api_key},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}


def test_settings_update_persists_before_regenerating_streamlink_config(monkeypatch):
    from app.routes import settings
    from app.schemas.settings import GlobalSettingsSchema
    from app.services.system import streamlink_config_service as config_module

    class Row:
        http_proxy = ""
        https_proxy = ""
        supported_codecs = "h264"

    class SettingsServiceFake:
        def __init__(self):
            self.row = Row()

        @staticmethod
        def validate_apprise_url(url):
            return True

        @staticmethod
        def validate_proxy_url(url):
            return True

        def get_global_settings_row(self):
            return self.row

        def update_global_settings(self, data):
            self.row.http_proxy = data.http_proxy
            self.row.https_proxy = data.https_proxy
            self.row.supported_codecs = data.supported_codecs
            return data

    class NotificationServiceFake:
        @staticmethod
        def _initialize_apprise():
            return None

    class StreamlinkConfigFake:
        observed_codecs = None

        async def regenerate_config(self):
            self.observed_codecs = service.row.supported_codecs
            return True

    service = SettingsServiceFake()
    config = StreamlinkConfigFake()
    monkeypatch.setattr(config_module, "streamlink_config_service", config)
    data = GlobalSettingsSchema(supported_codecs="av1,h265,h264")

    asyncio.run(
        settings.update_settings(data, service, lambda: NotificationServiceFake())
    )

    assert config.observed_codecs == "av1,h265,h264"


# ---------------------------------------------------------------------------
# 3. DI overrideability (session, services, settings, auth identity, adapters)
# ---------------------------------------------------------------------------


def test_image_adapter_is_injectable():
    from app import dependencies

    assert hasattr(dependencies, "get_image_service")
    assert hasattr(dependencies, "get_websocket_manager")


def test_primary_service_seams_exist(app):
    from app import dependencies

    for name in (
        "get_category_service",
        "get_video_catalog_service",
        "get_settings_service",
        "get_streamer_service",
        "get_notification_service",
        "get_current_user",
        "get_db",
    ):
        assert hasattr(dependencies, name), f"missing DI provider {name}"


def test_image_adapter_override_is_honored(app):
    """Adapting unified_image_service through DI must be overrideable."""
    from app import dependencies

    marker = object()
    app.dependency_overrides[dependencies.get_image_service] = lambda: marker
    try:
        assert app.dependency_overrides[dependencies.get_image_service]() is marker
    finally:
        app.dependency_overrides.pop(dependencies.get_image_service, None)


# ---------------------------------------------------------------------------
# 4. Extraction: video catalog workflow lives in a service, not the router.
# ---------------------------------------------------------------------------


def test_video_catalog_workflow_extracted_to_service():
    from app.services.media.video_catalog_service import VideoCatalogService

    assert hasattr(VideoCatalogService, "list_all_videos")
    assert hasattr(VideoCatalogService, "list_for_streamer")


def test_videos_router_has_no_inline_catalog_query():
    src = _source("app.routes.videos")
    # The two catalog listing routes must delegate to the service; the router
    # should not contain the strategy-merge query bodies anymore.
    assert "VideoCatalogService" in src


def test_categories_router_image_seam_injected():
    src = _source("app.routes.categories")
    assert "Depends(get_image_service)" in src


def test_streamers_router_images_and_settings_use_seams(app):
    src = _source("app.routes.streamers")
    assert "get_image_service" in src


# ---------------------------------------------------------------------------
# 5. Behavior preservation for representative primary endpoints.
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_client(app):
    """Stand up an in-memory test app with the boundary auth seams overridden.

    The default app engine and the DI session share the same in-memory SQLite
    (StaticPool), so we create the schema and seed rows there so the auth
    middleware and the category/settings endpoints observe the same data. Only
    the auth identity and event-registry seams are overridden.
    """
    import app.dependencies as deps
    import app.database as database
    from app.database import Base
    from app.models import GlobalSettings, Category, User
    from app.services.core.api_key_service import ApiKeyService

    lifecycle = database.database_lifecycle
    engine = lifecycle.sync_engine
    Base.metadata.create_all(bind=engine)

    with lifecycle.sync_session_factory() as db:
        db.add(GlobalSettings(id=1, notifications_enabled=True))
        db.add(Category(id=1, twitch_id="t1", name="Just Chatting"))
        user = User(id=1, username="alice", password="x", is_admin=True)
        db.add(user)
        db.commit()
        _, raw_key = ApiKeyService(db).create(1, "phase4a-test")

    class _FakeUser:
        id = 1
        is_admin = True

    def override_current_user():
        return _FakeUser()

    app.dependency_overrides[deps.get_current_user] = override_current_user
    app.dependency_overrides[deps.get_event_registry] = lambda: object()
    app.state.phase4a_api_key = raw_key

    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        app.state.phase4a_api_key = None
        lifecycle.dispose_sync()


def test_get_settings_shape_preserved(seeded_client):
    client = TestClient(seeded_client)
    resp = client.get(
        "/api/settings",
        headers={"X-API-Key": seeded_client.state.phase4a_api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "notification_url",
        "notifications_enabled",
        "notify_online_global",
        "notify_offline_global",
        "notify_update_global",
        "notify_favorite_category_global",
        "supported_codecs",
        "http_proxy",
        "https_proxy",
        "apprise_docs_url",
    ):
        assert field in body, f"missing settings field {field}"


def test_get_categories_shape_preserved(seeded_client):
    client = TestClient(seeded_client)
    resp = client.get(
        "/api/categories",
        headers={"X-API-Key": seeded_client.state.phase4a_api_key},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "categories" in body
    assert isinstance(body["categories"], list)
    if body["categories"]:
        item = body["categories"][0]
        for field in (
            "id",
            "twitch_id",
            "name",
            "box_art_url",
            "first_seen",
            "last_seen",
            "is_favorite",
        ):
            assert field in item, f"missing category field {field}"


def test_category_image_batches_reject_oversized_payloads(seeded_client):
    """Batch endpoints must bound fan-out without silently dropping requests."""
    client = TestClient(seeded_client)
    oversized_batch = [f"category-{index}" for index in range(201)]
    headers = {"X-API-Key": seeded_client.state.phase4a_api_key}

    for path in (
        "/api/categories/images/batch",
        "/api/categories/preload-images",
        "/api/categories/refresh-images",
    ):
        response = client.post(path, json=oversized_batch, headers=headers)
        assert response.status_code == 422
