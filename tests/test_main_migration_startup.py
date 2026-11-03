import os
import shutil
import sys
from types import SimpleNamespace

import pytest


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
@pytest.mark.parametrize("legacy_image_failure", [False, True])
async def test_lifespan_uses_factory_service_overrides_for_startup_and_shutdown(
    monkeypatch,
    tmp_path,
    caplog,
    legacy_image_failure,
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
    if legacy_image_failure:
        from app.models import Streamer
        from app.services.migration.image_migration_service import ImageMigrationService
        from app.utils import async_db_utils

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

        async def streamers():
            return [Streamer(id=123, username="synthetic")]

        def denied(*args, **kwargs):
            raise PermissionError("synthetic copy denied")

        monkeypatch.setattr(async_db_utils, "get_all_streamers", streamers)
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
        if legacy_image_failure:
            assert source.read_bytes() == b"synthetic-source"
            assert target.read_bytes() == b"synthetic-target"
            assert "Migration completed with errors" in caplog.text
            assert list(target.parent.iterdir()) == [target]

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
