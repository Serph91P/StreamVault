"""Recording producers must use the log owner selected by their real app factory."""

import importlib
import json
from datetime import datetime, timezone
from threading import get_ident

import pytest

from app.dependencies import _get_application_recording_manager
from app.config.logging_config import request_context
from app.lifespan import _close_application_proxy, _close_application_twitch
from app.utils.async_db_utils import run_in_thread_pool
from tests import test_logging_application_ownership

image_applications = test_logging_application_ownership.image_applications
logging_applications = test_logging_application_ownership.logging_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["start", "stop"])
async def test_real_lifecycle_log_call_is_off_loop(
    logging_applications, monkeypatch, operation
):
    from app.models import Recording, Stream

    apps, databases, _, roots, _, observed = logging_applications

    def seed():
        with databases[0].sync_session_factory() as session:
            session.add(Stream(id=71, streamer_id=1, title="local logging boundary"))
            session.flush()
            if operation == "stop":
                session.add(
                    Recording(
                        id=72,
                        stream_id=71,
                        start_time=datetime.now(timezone.utc),
                        status="recording",
                        path="/scope/recording.ts",
                    )
                )
            session.commit()

    await run_in_thread_pool(seed)
    try:
        manager = await run_in_thread_pool(_get_application_recording_manager, apps[0])
        lifecycle = manager._service.orchestrator.lifecycle_manager

        async def unavailable_process(*_args, **_kwargs):
            return False

        if operation == "start":
            monkeypatch.setattr(
                lifecycle, "_start_recording_process", unavailable_process
            )
        else:
            monkeypatch.setattr(
                lifecycle, "_stop_recording_process", unavailable_process
            )
            lifecycle.state_manager.add_active_recording(
                72,
                {"streamer_id": 1, "stream_id": 71, "file_path": "/scope/recording.ts"},
            )
            publisher = importlib.import_module(
                "app.services.recording.database_event_orphaned_recovery"
            )

            async def publish(*_args, **_kwargs):
                return None

            monkeypatch.setattr(publisher, "on_recording_status_changed", publish)
        observed.clear()
        if operation == "start":
            assert await lifecycle.start_recording(71, 1, quality="best") is None
        else:
            assert await lifecycle.stop_recording(72) is False
        assert observed and get_ident() not in observed

        def contents():
            return "\n".join(path.read_text() for path in roots[0].rglob("*.log"))

        assert f"RECORDING_{operation.upper()}" in await run_in_thread_pool(contents)
        assert databases[0].sync_engine.pool.checkedout() == 0
    finally:
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("log_format", ["text", "json"])
async def test_recording_component_preserves_redaction_and_configured_context(
    logging_applications, log_format
):
    apps, _, _, roots, _, _ = logging_applications
    apps[0].state.settings.LOG_FORMAT = log_format
    token = request_context.set("recording-context-probe")
    try:
        manager = await run_in_thread_pool(_get_application_recording_manager, apps[0])
        await run_in_thread_pool(
            manager._service.recording_logger.log_recording_error,
            1,
            "shared",
            "Authorization=Bearer fixture-private-value",
        )

        def read_record():
            return [
                line
                for path in roots[0].rglob("*.log")
                for line in path.read_text().splitlines()
                if "RECORDING_ERROR" in line
            ]

        lines = await run_in_thread_pool(read_record)
        assert len(lines) == 1
        assert "fixture-private-value" not in lines[0]
        if log_format == "json":
            record = json.loads(lines[0])
            assert record["request_id"] == "recording-context-probe"
            assert record["level"] == "ERROR"
            assert "RECORDING_ERROR" in record["message"]
    finally:
        request_context.reset(token)
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "start",
        "stop",
        "stream",
        "metadata",
        "configuration",
        "file",
        "process",
        "cleanup",
    ],
)
async def test_factory_recording_producers_write_only_owned_logs(
    logging_applications, monkeypatch, tmp_path, operation
):
    apps, _, _, roots, _, observed = logging_applications
    module = importlib.import_module("app.services.system.logging_service")
    legacy_root = tmp_path / "standalone-legacy"
    legacy = await run_in_thread_pool(
        module.LoggingService, logs_base_dir=str(legacy_root), isolated=True
    )
    monkeypatch.setattr(module, "_logging_service_instance", legacy)
    try:
        managers = [
            await run_in_thread_pool(_get_application_recording_manager, app)
            for app in apps
        ]
        for index, manager in enumerate(managers):
            writer = manager._service.recording_logger
            marker = f"owned-event-{index}"
            observed.clear()
            if operation == "start":
                await run_in_thread_pool(
                    writer.log_recording_start,
                    1,
                    "shared",
                    "best",
                    f"/{marker}/recording.ts",
                )
            elif operation == "stop":
                await run_in_thread_pool(
                    writer.log_recording_stop,
                    1,
                    "shared",
                    10,
                    f"/{marker}/recording.ts",
                )
            elif operation == "stream":
                await run_in_thread_pool(
                    writer.log_stream_detection, "shared", True, {"title": marker}
                )
            elif operation == "metadata":
                await run_in_thread_pool(
                    writer.log_metadata_operation, "shared", "metadata", True, marker
                )
            elif operation == "configuration":
                await run_in_thread_pool(
                    writer.log_configuration_change, "quality", "best", marker
                )
            elif operation == "file":
                await run_in_thread_pool(
                    writer.log_file_operation,
                    "probe",
                    "/recordings/shared/probe.mp4",
                    True,
                    marker,
                )
            elif operation == "process":
                await run_in_thread_pool(
                    writer.log_process_monitoring, "shared", "probe", marker
                )
            else:
                await run_in_thread_pool(
                    writer.log_cleanup_operation, "shared", 1, 2, marker
                )

            def contents(root):
                return "\n".join(path.read_text() for path in root.rglob("*.log"))

            own = await run_in_thread_pool(contents, roots[index])
            peer = await run_in_thread_pool(contents, roots[1 - index])
            standalone = await run_in_thread_pool(contents, legacy_root)
            assert marker in own
            assert marker not in peer
            assert marker not in standalone
    finally:
        for app in apps:
            await _close_application_proxy(app)
            await _close_application_twitch(app)
        await run_in_thread_pool(legacy.close)
