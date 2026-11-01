import sys
import threading
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("migration_success", [False, True])
async def test_configured_lifespan_migrates_and_disposes_only_its_database_off_loop(
    monkeypatch, tmp_path, migration_success
):
    from app import lifespan as module
    from app.config.settings import get_settings
    from app.database import DatabaseLifecycle
    from app.services.system.migration_service import MigrationService
    import app.services.system.persistent_key_service as key_module

    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'owned.db'}")
    bound_calls = []
    foreign_disposals = []
    key_calls = []
    event_loop_thread = threading.get_ident()

    class FailedMigrations:
        @staticmethod
        def run_safe_migrations():
            return migration_success

    def bind(engine):
        bound_calls.append((engine, threading.get_ident()))
        return FailedMigrations

    def forbidden_default():
        raise AssertionError("Configured application used process-default migrations")

    def forbidden_default_keys():
        raise AssertionError("Configured application used process-default keys")

    class ScopedKeys:
        def __init__(self, factory):
            self.factory = factory

        def bootstrap(self, configuration):
            key_calls.append((self.factory, configuration, threading.get_ident()))
            raise RuntimeError("scoped bootstrap stop")

    async def foreign_dispose():
        foreign_disposals.append(True)

    monkeypatch.setattr(MigrationService, "for_engine", staticmethod(bind))
    monkeypatch.setattr(
        MigrationService, "run_safe_migrations", staticmethod(forbidden_default)
    )
    monkeypatch.setattr(key_module, "bootstrap_persistent_keys", forbidden_default_keys)
    monkeypatch.setattr(key_module, "PersistentKeyBootstrapService", ScopedKeys)
    monkeypatch.setattr(
        module, "database_lifecycle", SimpleNamespace(adispose=foreign_dispose)
    )
    application = SimpleNamespace(
        state=SimpleNamespace(
            database_lifecycle=lifecycle,
            settings=get_settings().model_copy(
                update={"RECORDING_DIRECTORY": str(tmp_path / "recordings")}
            ),
        ),
        dependency_overrides={},
    )
    try:
        expected = (
            "scoped bootstrap stop"
            if migration_success
            else "Database migrations did not complete successfully"
        )
        with pytest.raises(RuntimeError, match=expected):
            async with module.lifespan(application):
                pytest.fail("Failed migration must not reach ready")
        assert len(bound_calls) == 1
        assert bound_calls[0][1] != event_loop_thread
        if migration_success:
            assert len(key_calls) == 1
            assert key_calls[0][0].kw["bind"] is bound_calls[0][0]
            assert key_calls[0][1] is application.state.settings
            assert key_calls[0][2] != event_loop_thread
        else:
            assert key_calls == []
        assert foreign_disposals == []
        assert lifecycle._sync_engine is None
    finally:
        await lifecycle.adispose()


@pytest.mark.asyncio
async def test_lifespan_fails_startup_when_database_migrations_fail(monkeypatch):
    from app.main import lifespan
    from app.services.system.migration_service import MigrationService

    monkeypatch.setattr(
        MigrationService,
        "run_safe_migrations",
        staticmethod(lambda: False),
    )

    with pytest.raises(
        RuntimeError, match="Database migrations did not complete successfully"
    ):
        await lifespan(None).__aenter__()


@pytest.mark.asyncio
async def test_lifespan_uses_factory_service_overrides_for_startup_and_shutdown(
    monkeypatch,
):
    from app import dependencies
    from app import lifespan as lifespan_module
    from app.services.system.migration_service import MigrationService

    calls = []

    class RecordingManager:
        async def reconcile_leases(self):
            calls.append("reconcile")
            return 0

        async def shutdown(self, timeout):
            calls.append(("recording-shutdown", timeout))

    class EventRegistry:
        eventsub = None

        async def initialize_eventsub(self):
            calls.append("eventsub-initialize")

    async def record(name):
        calls.append(name)

    async def event_registry_override():
        return EventRegistry()

    monkeypatch.setattr(
        MigrationService, "run_safe_migrations", staticmethod(lambda: True)
    )

    monkeypatch.setattr(
        lifespan_module,
        "image_sync_service",
        SimpleNamespace(
            start_sync_worker=lambda: record("image-sync-start"),
            stop_sync_worker=lambda: record("image-sync-stop"),
        ),
    )
    monkeypatch.setattr(
        lifespan_module,
        "websocket_broadcast_task",
        SimpleNamespace(
            start=lambda: record("websocket-start"),
            stop=lambda: record("websocket-stop"),
        ),
    )
    monkeypatch.setattr(
        lifespan_module,
        "database_lifecycle",
        SimpleNamespace(
            adispose=lambda: record("database-dispose"),
        ),
    )

    async def config_update():
        return True

    module_overrides = {
        "app.services.system.persistent_key_service": SimpleNamespace(
            bootstrap_persistent_keys=lambda: calls.append("keys-bootstrap")
        ),
        "app.services.migration.image_migration_service": SimpleNamespace(
            image_migration_service=SimpleNamespace(
                old_images_dir=SimpleNamespace(exists=lambda: False),
                old_artwork_dir=SimpleNamespace(exists=lambda: False),
            )
        ),
        "app.services.system.streamlink_config_service": SimpleNamespace(
            streamlink_config_service=SimpleNamespace(
                update_config_from_settings=config_update
            )
        ),
        "app.services.images.image_refresh_service": SimpleNamespace(
            image_refresh_service=SimpleNamespace(
                check_and_refresh_missing_images=lambda: record("image-refresh")
            )
        ),
        "app.services.system.logging_service": SimpleNamespace(
            logging_service=SimpleNamespace(
                _schedule_cleanup=lambda interval_hours: record("log-cleanup")
            )
        ),
        "app.services.init.startup_init": SimpleNamespace(
            initialize_background_services=lambda supervisor: record("background-init"),
            shutdown_background_services=lambda: record("background-stop"),
        ),
        "app.services.proxy.proxy_health_service": SimpleNamespace(
            proxy_health_service=SimpleNamespace(
                start=lambda: record("proxy-start"), stop=lambda: record("proxy-stop")
            )
        ),
        "app.services.live_streaming_service": SimpleNamespace(
            live_streaming_service=SimpleNamespace(stop=lambda: record("live-stop"))
        ),
        "app.services.background_queue_service": SimpleNamespace(
            background_queue_service=SimpleNamespace(stop=lambda: record("queue-stop"))
        ),
    }
    for module_name, module in module_overrides.items():
        monkeypatch.setitem(sys.modules, module_name, module)

    app = SimpleNamespace(
        state=SimpleNamespace(),
        dependency_overrides={
            dependencies.get_recording_manager: RecordingManager,
            dependencies.get_event_registry: event_registry_override,
        },
    )

    async with lifespan_module.lifespan(app):
        assert app.state.recording_manager.__class__ is RecordingManager
        assert app.state.startup_phases == [
            "migrations",
            "persistent-identities",
            "optional-preparation",
            "core-services",
            "background-services",
            "ready",
        ]

    assert calls.index("reconcile") < calls.index("eventsub-initialize")
    shutdown_calls = [
        "proxy-stop",
        "websocket-stop",
        "image-sync-stop",
        "background-stop",
        "live-stop",
        ("recording-shutdown", lifespan_module.TIMEOUTS.GRACEFUL_SHUTDOWN),
        "database-dispose",
    ]
    assert [calls.index(call) for call in shutdown_calls] == sorted(
        calls.index(call) for call in shutdown_calls
    )
    assert any(
        call[0] == "recording-shutdown" for call in calls if isinstance(call, tuple)
    )
