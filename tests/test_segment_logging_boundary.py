"""Native startup log I/O and failure diagnostics must stay with each app owner.

Value: protects=owned startup/failure logs, filesystem worker boundary and child reaping;
fails_when=FileHandler I/O runs on loop or equal-name apps exchange failure diagnostics;
why_new=lifecycle logging tests replace startup before the direct FileHandler branch;
seam=none; no_claim=Twitch/provider capture; spawn port runs real local children.
"""

import asyncio
import builtins
import logging
import os
from pathlib import Path
import sys
from threading import get_ident

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.models import Stream, Streamer
from app.services.recording.exceptions import ProcessError
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["running", "failed", "same-name-pair"])
async def test_native_segment_start_prepares_owned_log_files_in_worker(
    image_applications, monkeypatch, mode
):
    apps, databases, _clients, _ = image_applications
    for app in apps:
        app.state.settings.LOGS_BASE_DIR = (
            app.state.settings.RECORDING_DIRECTORY + "/.logs"
        )
        app.state.settings.TWITCH_OAUTH_TOKEN = ""
    roots = [Path(app.state.settings.LOGS_BASE_DIR) for app in apps]
    contexts = []
    for index in range(2 if mode == "same-name-pair" else 1):
        with databases[index].sync_session_factory() as db:
            db.get(Streamer, 1).username = "shared-segment"
            db.add(Stream(id=70, streamer_id=1))
            db.commit()
        manager = await run_in_thread_pool(
            get_application_recording_manager,
            HTTPConnection({"type": "http", "app": apps[index], "headers": []}),
        )
        lifecycle = manager.orchestrator.lifecycle_manager
        stream = await lifecycle.database_service.get_stream_by_id(70)
        output = str(
            Path(apps[index].state.settings.RECORDING_DIRECTORY) / "capture.ts"
        )
        info = await lifecycle.process_manager._initialize_segmented_recording(
            stream, output, "best", None
        )
        contexts.append((lifecycle.process_manager, stream, info))
    loop_thread = get_ident()
    opened, stats, children, log_files = [], [], [], []
    native_open, native_stat = builtins.open, os.stat
    native_spawn = asyncio.create_subprocess_exec
    peer_spawned = asyncio.Event()
    first_segment = contexts[0][2]["current_segment_path"]

    def observed_open(path, *args, **kwargs):
        file = native_open(path, *args, **kwargs)
        if isinstance(path, (str, bytes, os.PathLike)) and any(
            os.fsdecode(path).startswith(str(root) + os.sep) for root in roots
        ):
            opened.append(get_ident())
            log_files.append(file)
        return file

    def observed_stat(path, *args, **kwargs):
        if (
            isinstance(path, (str, bytes, os.PathLike))
            and os.fsdecode(path) == first_segment
        ):
            stats.append(get_ident())
        return native_stat(path, *args, **kwargs)

    async def local_spawn(*args, **kwargs):
        own = any(first_segment in str(arg) for arg in args)
        fail = mode == "failed" or (mode == "same-name-pair" and own)
        script = (
            "print('native-own-failure',flush=True);raise SystemExit(7)"
            if fail
            else "import time;print('local capture ready',flush=True);time.sleep(60)"
        )
        child = await native_spawn(sys.executable, "-c", script, **kwargs)
        children.append(child)
        if mode == "same-name-pair":
            if own:
                await child.wait()
                await asyncio.wait_for(peer_spawned.wait(), 3)
            else:
                peer_spawned.set()
        return child

    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(builtins, "open", observed_open)
            scoped.setattr(os, "stat", observed_stat)
            scoped.setattr(asyncio, "create_subprocess_exec", local_spawn)
            results = await asyncio.gather(
                *(
                    pm._start_segment(
                        stream, info["current_segment_path"], "best", info
                    )
                    for pm, stream, info in contexts
                ),
                return_exceptions=True,
            )
        if mode == "running":
            assert results[0] is not None and results[0].returncode is None
        else:
            assert isinstance(results[0], ProcessError)
            assert any(child.returncode == 7 for child in children)
        own_text = "\n".join(path.read_text() for path in roots[0].rglob("*.log"))
        assert "Starting streamlink recording" in own_text
        if mode == "same-name-pair":
            assert results[1] is not None and results[1].returncode is None
            peer_text = "\n".join(path.read_text() for path in roots[1].rglob("*.log"))
            assert "PROCESS FAILED IMMEDIATELY" not in peer_text
            assert "PROCESS FAILED IMMEDIATELY" in own_text
            assert "native-own-failure" not in peer_text
        else:
            assert not roots[1].exists()
        assert opened and loop_thread not in opened
        assert log_files and all(file.closed for file in log_files)
        assert loop_thread not in stats
        if mode != "running":
            assert stats
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        await close_owned(apps)
        for logger in logging.Logger.manager.loggerDict.values():
            if isinstance(logger, logging.Logger):
                for handler in list(logger.handlers):
                    if isinstance(handler, logging.FileHandler) and any(
                        handler.baseFilename.startswith(str(root) + os.sep)
                        for root in roots
                    ):
                        logger.removeHandler(handler)
                        handler.close()
