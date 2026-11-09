import os
import shutil
import sys
import threading
from types import SimpleNamespace

import pytest
from starlette.websockets import WebSocket, WebSocketState

from app.services.communication.websocket_manager import ConnectionManager


async def connected_manager():
    async def receive():
        return {"type": "websocket.connect"}

    async def send(_message):
        pass

    socket = WebSocket(
        {"type": "websocket", "headers": [], "client": ("127.0.0.1", 12345)},
        receive,
        send,
    )
    manager = ConnectionManager()
    assert await manager.connect(socket)
    return manager, socket


@pytest.mark.asyncio
@pytest.mark.parametrize("migration_success", [False, True])
@pytest.mark.parametrize("shares_default_handle", [False, True])
async def test_configured_lifespan_migrates_and_disposes_only_its_database_off_loop(
    monkeypatch, tmp_path, migration_success, shares_default_handle
):
    from app import lifespan as module
    from app.config.settings import get_settings
    from app.database import DatabaseLifecycle
    from app.services.system.migration_service import MigrationService
    import app.services.system.persistent_key_service as key_module

    lifecycle = DatabaseLifecycle(f"sqlite:///{tmp_path / 'owned.db'}")
    own_manager, own_socket = await connected_manager()
    peer_manager, peer_socket = await connected_manager()
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
        module,
        "database_lifecycle",
        lifecycle
        if shares_default_handle
        else SimpleNamespace(adispose=foreign_dispose),
    )
    application = SimpleNamespace(
        state=SimpleNamespace(
            legacy_default=False,
            database_lifecycle=lifecycle,
            websocket_manager=own_manager,
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
        assert own_socket.application_state == WebSocketState.DISCONNECTED
        assert not own_manager.active_connections and not own_manager._sender_tasks
        assert peer_socket.application_state == WebSocketState.CONNECTED
        assert len(peer_manager.active_connections) == 1
    finally:
        await own_manager.close_all()
        await peer_manager.close_all()
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
@pytest.mark.parametrize("owned_images", [False, True])
@pytest.mark.parametrize("legacy_image_failure", [False, True])
@pytest.mark.parametrize("owned_logging", [False, True])
async def test_lifespan_uses_factory_service_overrides_for_startup_and_shutdown(
    monkeypatch,
    owned_images,
    tmp_path,
    caplog,
    legacy_image_failure,
    owned_logging,
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
        calls.append("legacy-config-update")
        return True

    from app.utils import proxy_encryption

    proxy_bootstraps = []

    def proxy_bootstrap(factory):
        proxy_bootstraps.append((factory, threading.get_ident()))
        calls.append("proxy-identities")

    monkeypatch.setattr(proxy_encryption, "bootstrap_proxy_identity", proxy_bootstrap)

    async def background_init(
        supervisor,
        session_factory,
        settings,
        recording_manager,
        twitch_api,
        image_sync_service=None,
    ):
        assert isinstance(recording_manager, RecordingManager)
        assert twitch_api is None  # This wiring fixture has no factory HTTP slot.
        if owned_images:
            assert image_sync_service is app.state.auto_image_sync_service
            await image_sync_service.start_sync_worker()
        else:
            assert image_sync_service is None
        await record("background-init")

    async def background_stop(supervisor, image_sync_service=None):
        if owned_images:
            assert image_sync_service is app.state.auto_image_sync_service
            await image_sync_service.stop_sync_worker()
        else:
            assert image_sync_service is None
        await record("background-stop")

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
            initialize_background_services=background_init,
            shutdown_background_services=background_stop,
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
    if legacy_image_failure:
        from app.services.migration.image_migration_service import (
            ImageMigrationService,
            MigrationStreamer,
        )

        image_service = ImageMigrationService()
        image_service.recordings_dir = tmp_path
        image_service.old_images_dir = tmp_path / ".images"
        image_service.old_artwork_dir = tmp_path / ".artwork"
        (tmp_path / "synthetic").mkdir()
        source = tmp_path / ".artwork/synthetic/poster.jpg"
        target = tmp_path / ".media/artwork/synthetic/poster.jpg"
        source.parent.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        source.write_bytes(b"synthetic-source")
        target.write_bytes(b"synthetic-target")
        os.utime(target, (100, 100))
        os.utime(source, (200, 200))

        def streamers():
            return [MigrationStreamer(id=123, username="synthetic")]

        def denied(*args, **kwargs):
            raise PermissionError("synthetic copy denied")

        monkeypatch.setattr(image_service, "_streamers", streamers)
        monkeypatch.setattr(shutil, "copyfile", denied)
        module_overrides["app.services.migration.image_migration_service"] = (
            SimpleNamespace(image_migration_service=image_service)
        )
    for module_name, module in module_overrides.items():
        monkeypatch.setitem(sys.modules, module_name, module)

    app = SimpleNamespace(
        state=SimpleNamespace(),
        dependency_overrides={
            dependencies.get_recording_manager: RecordingManager,
            dependencies.get_event_registry: event_registry_override,
        },
    )

    constructor_threads = []
    config_threads = []
    streams = []
    if owned_logging:
        from threading import Lock
        from app.config.settings import get_settings

        app.state.settings = get_settings().model_copy(
            update={"LOGS_BASE_DIR": str(tmp_path / "owned-logs")}
        )
        app.state.logging_service = None
        app.state.logging_service_lock = Lock()
        app.state.streamlink_config_service_lock = Lock()

        async def owned_config_update():
            calls.append("owned-config-update")
            return True

        def owned_config(_app):
            config_threads.append(threading.get_ident())
            return SimpleNamespace(update_config_from_settings=owned_config_update)

        monkeypatch.setattr(
            lifespan_module,
            "_get_application_streamlink_config_service",
            owned_config,
            raising=False,
        )
        native_logging = dependencies.LoggingService

        class ObservedLogging(native_logging):
            def __init__(self, *args, **kwargs):
                constructor_threads.append(threading.get_ident())
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(dependencies, "LoggingService", ObservedLogging)

    if owned_images:
        from threading import Lock
        from app.services.images.image_sync_service import ImageSyncService
        from app.services.images.auto_image_sync_service import AutoImageSyncService

        app.state.image_sync_service = ImageSyncService()
        app.state.proxy_health_service_lock = Lock()
        owned_proxy = SimpleNamespace(
            start=lambda: record("owned-proxy-start"),
            stop=lambda: record("proxy-stop"),
        )
        app.dependency_overrides[dependencies.get_proxy_health_service] = lambda: (
            owned_proxy
        )
        app.state.auto_image_sync_service = AutoImageSyncService()
        app.state.auto_image_sync_service_lock = Lock()
        monkeypatch.setattr(
            lifespan_module,
            "_get_application_auto_image_sync_service",
            lambda _: app.state.auto_image_sync_service,
        )
        app.state.image_sync_service_lock = Lock()
        app.state.image_service_lock = Lock()

        def migration_owner(_):
            calls.append("owned-image-migration")
            return module_overrides[
                "app.services.migration.image_migration_service"
            ].image_migration_service

        monkeypatch.setattr(
            lifespan_module,
            "_get_application_image_migration_service",
            migration_owner,
            raising=False,
        )
        monkeypatch.setattr(
            lifespan_module,
            "_get_application_image_refresh_service",
            lambda _: SimpleNamespace(
                check_and_refresh_missing_images=lambda: record("owned-image-refresh")
            ),
            raising=False,
        )
        native_stop = app.state.image_sync_service.stop_sync_worker

        async def owned_stop():
            await native_stop()
            await record("image-sync-stop")

        app.state.image_sync_service.stop_sync_worker = owned_stop

    async with lifespan_module.lifespan(app):
        assert len(proxy_bootstraps) == 1
        assert proxy_bootstraps[0][1] != threading.get_ident()
        assert (
            calls.index("keys-bootstrap")
            < calls.index("proxy-identities")
            < calls.index("reconcile")
        )
        if owned_logging:
            assert "owned-config-update" in calls
            assert "legacy-config-update" not in calls
            assert config_threads and threading.get_ident() not in config_threads
            actor = app.state.logging_service
            assert actor is not None
            assert str(actor.logs_base_dir) == str(tmp_path / "owned-logs")
            periodic = app.state.task_supervisor._tasks["log-cleanup"].get_coro()
            assert periodic.cr_frame is not None
            assert periodic.cr_frame.f_locals.get("self") is actor
            streams = [
                handler.stream
                for component in (
                    actor.streamlink_logger,
                    actor.ffmpeg_logger,
                    actor.recording_logger,
                )
                for handler in component.handlers
            ]
        if owned_images:
            assert app.state.image_sync_service.is_running()
            assert app.state.auto_image_sync_service.is_running()
            assert "image-sync-start" not in calls
            assert "owned-image-refresh" in calls
            assert "owned-image-migration" in calls
            assert "owned-proxy-start" in calls
            assert "proxy-start" not in calls
            assert "image-refresh" not in calls
        assert app.state.recording_manager.__class__ is RecordingManager
        if legacy_image_failure:
            assert source.read_bytes() == b"synthetic-source"
            assert target.read_bytes() == b"synthetic-target"
            assert "Migration completed with errors" in caplog.text
            assert list(target.parent.iterdir()) == [target]
        assert app.state.startup_phases == [
            "migrations",
            "persistent-identities",
            "optional-preparation",
            "core-services",
            "background-services",
            "ready",
        ]

    if owned_logging:
        assert len(constructor_threads) == 1
        assert constructor_threads[0] != threading.get_ident()
        assert app.state.logging_service is None
        assert streams and all(stream.closed for stream in streams)
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
