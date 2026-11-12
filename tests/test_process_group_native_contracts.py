"""Actual OS process-group stop verifies identities and leaves peer children alone.

Value: protects=group/fingerprint checks and actual stop/permission failure reaping;
fails_when=wrong/stale identity receives a signal or denied stop reports success;
why_new=rotation tests substitute this group helper; stop-admission covers different branch;
seam=none; no_claim=provider acquisition, activated lease fencing or media finalization.
"""

import asyncio
import os
import sys

import pytest
from starlette.requests import HTTPConnection

from app.dependencies import get_application_recording_manager
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_image_http_ownership import image_applications as image_applications
from tests.test_processing_callback_ownership import close_owned


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["match", "wrong-group", "stale-fingerprint", "pre-exited", "signal-denied"]
)
async def test_native_process_group_identity_and_denial_preserve_peer(
    image_applications, monkeypatch, case
):
    apps, _databases, _clients, _ = image_applications
    manager = await run_in_thread_pool(
        get_application_recording_manager,
        HTTPConnection({"type": "http", "app": apps[0], "headers": []}),
    )
    pm = manager.orchestrator.lifecycle_manager.process_manager
    children = []
    denied = []
    try:
        for _ in range(2):
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);print('ready',flush=True);time.sleep(60)",
                stdout=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            children.append(child)
            assert child.stdout is not None
            assert await asyncio.wait_for(child.stdout.readline(), 3) == b"ready\n"
        owned, peer = children
        identity = await pm.upstream_coordinator.inspect_process_identity(owned.pid)
        assert identity.process_group_id == owned.pid
        group = peer.pid if case == "wrong-group" else identity.process_group_id
        fingerprint = (
            identity.fingerprint + "-stale" if case == "stale-fingerprint" else None
        )
        if case == "pre-exited":
            owned.kill()
            await owned.wait()
        native_killpg = os.killpg

        def refused_signal(pgid, sig):
            if pgid == owned.pid:
                denied.append((pgid, sig))
                raise PermissionError("synthetic-owned-group-signal-denied")
            return native_killpg(pgid, sig)

        with monkeypatch.context() as scoped:
            if case == "signal-denied":
                scoped.setattr(os, "killpg", refused_signal)
            result = await pm._terminate_process_group(owned, group, 0.05, fingerprint)
        if case in {"match", "pre-exited"}:
            assert result is True and owned.returncode is not None
            assert owned.returncode < 0
        else:
            assert result is False and owned.returncode is None
        assert peer.returncode is None
        if case == "signal-denied":
            assert denied and all(pgid == owned.pid for pgid, _sig in denied)
    finally:
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
        await close_owned(apps)
