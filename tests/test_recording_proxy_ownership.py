"""Recording child admission reads proxy policy only from its application."""

import importlib
import sys
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app import dependencies
from app.models import GlobalSettings, ProxySettings, RecordingSettings, Stream
from app.services.recording.exceptions import ProcessError
from app.services.system.twitch_token_service import RecordingTokenResolution
from app.utils.async_db_utils import run_in_thread_pool
from app.utils.streamlink_utils import get_streamlink_command
from tests import test_proxy_http_ownership

proxy_applications = test_proxy_http_ownership.proxy_applications
image_applications = test_proxy_http_ownership.image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", ["healthy", "direct", "blocked", "stored"])
async def test_recording_segment_uses_owned_proxy_policy_before_real_child_start(
    proxy_applications, monkeypatch, tmp_path, policy
):
    applications, databases, _, queries = proxy_applications
    module = importlib.import_module("app.services.recording.process_manager")
    commands = []
    actors = []

    def command(**kwargs):
        assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
        commands.append((kwargs, get_streamlink_command(**kwargs)))
        return [sys.executable, "-c", "import time; time.sleep(60)"]

    monkeypatch.setattr(module, "get_streamlink_command", command)
    try:
        for index, (app, database) in enumerate(
            zip(applications, databases, strict=True)
        ):
            with database.sync_session_factory() as session:
                session.add(Stream(id=1, streamer_id=1))
                settings = session.query(RecordingSettings).one()
                settings.enable_proxy = policy != "stored"
                settings.fallback_to_direct_connection = policy == "direct"
                proxy = session.get(ProxySettings, 1)
                proxy.health_status = "healthy" if policy == "healthy" else "failed"
                proxy.enabled = policy == "healthy"
                session.query(
                    GlobalSettings
                ).one().http_proxy = f"http://stored-{index}.invalid:8080"
                session.commit()
            connection = HTTPConnection({"type": "http", "app": app, "headers": []})
            actor = await run_in_thread_pool(
                dependencies.get_application_recording_manager, connection
            )
            actors.append(actor)
            stream = await actor.orchestrator.database_service.get_stream_by_id(1)
            actor.process_manager.logging_service = None
            queries.clear()
            path = str(tmp_path / f"owner-{index}.ts")
            info = {"segment_count": 1, "total_segments": []}
            resolution = RecordingTokenResolution(None, None, False, False, "fixture")
            if policy == "blocked":
                with pytest.raises(
                    ProcessError, match="Failed to start segment recording"
                ) as failure:
                    await actor.process_manager._start_segment(
                        stream, path, "480p", info, token_resolution=resolution
                    )
                assert isinstance(failure.value.__cause__, ProcessError)
                assert "No healthy proxies" in str(failure.value.__cause__)
                assert not commands
            else:
                child = await actor.process_manager._start_segment(
                    stream, path, "480p", info, token_resolution=resolution
                )
                assert child.returncode is None
                arguments, argv = commands[-1]
                expected = (
                    {
                        "http": f"http://owner-{index}.invalid:8080",
                        "https": f"http://owner-{index}.invalid:8080",
                    }
                    if policy == "healthy"
                    else {"http": f"http://stored-{index}.invalid:8080"}
                    if policy == "stored"
                    else None
                )
                assert arguments["proxy_settings"] == expected
                assert arguments["anonymous"] is True
                assert arguments["quality"] == "480p"
                assert arguments["output_path"] == path
                assert "--twitch-supported-codecs=h264" in argv
                await actor.process_manager.cleanup_all()
                assert child.returncode is not None
            relevant = [thread for thread, sql in queries if "settings" in sql]
            assert relevant and get_ident() not in relevant
            assert all(db.sync_engine.pool.checkedout() == 0 for db in databases)
    finally:
        for actor in actors:
            await actor.process_manager.cleanup_all()
        for app in applications:
            await app.state.background_queue_service.queue_manager.progress_tracker.cleanup_background_tasks()
