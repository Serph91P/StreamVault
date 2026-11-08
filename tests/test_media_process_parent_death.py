"""An app crash cannot leave a post-processing writer alive behind its journal."""

import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.background_task import BackgroundTask, BackgroundTaskDependency
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import TaskStatus

import psutil
import pytest


@pytest.mark.skipif(sys.platform != "linux", reason="Linux parent-death contract")
def test_real_ffmpeg_writer_dies_and_is_reaped_after_owning_app_sigkill(tmp_path):
    libc = ctypes.CDLL(None, use_errno=True)
    old = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0  # PR_GET_CHILD_SUBREAPER
    assert libc.prctl(36, 1, 0, 0, 0) == 0  # reap this test's orphan, not PID 1
    pid_path = tmp_path / "child.json"
    media = tmp_path / "writing.ts"
    journal = tmp_path / "jobs.db"
    engine = create_engine(f"sqlite:///{journal}")
    with engine.begin() as connection:
        connection.exec_driver_sql("BEGIN")
        BackgroundTask.__table__.create(connection)
        BackgroundTaskDependency.__table__.create(connection)
    code = '''
import asyncio,json,sys
from pathlib import Path
from app.utils.media_process import media_process
from app.utils.queue_ownership import queue_owner_fd
from app.services.queues.durable_task_store import DurableTaskStore
from app.services.queues.task_progress_tracker import QueueTask, TaskStatus, TaskPriority
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import socket
async def main():
    socket.gethostname = lambda: "synthetic-retired-container"
    store = DurableTaskStore(sessionmaker(create_engine("sqlite:///" + sys.argv[3])))
    job = QueueTask(id="synthetic-crash-job", task_type="mp4_remux", priority=TaskPriority.NORMAL, payload={}, status=TaskStatus.PENDING, created_at=datetime.now(timezone.utc))
    store.accept([(job, set(), "synthetic")])
    assert len(store.claim(1, set(), 1, True)) == 1
    queue_owner_fd.set(store.owner_fd)
    async with media_process("ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25", "-t", "60", "-c:v", "mpeg2video", "-b:v", "1M", "-f", "mpegts", "-y", sys.argv[2]) as (child, output):
        Path(sys.argv[1]).write_text(json.dumps({"pid":child.pid, "owner_fd":store.owner_fd}))
        await child.wait()
asyncio.run(main())
'''
    parent = subprocess.Popen([sys.executable, "-c", code, str(pid_path), str(media), str(journal)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    child = None
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            assert parent.poll() is None
            if pid_path.exists():
                child = psutil.Process(json.loads(pid_path.read_text())["pid"])
                if child.name() == "ffmpeg" and media.exists() and media.stat().st_size > 0:
                    break
            time.sleep(0.01)
        else:
            pytest.fail("real ffmpeg did not start writing")
        assert child is not None and child.is_running()
        inherited = json.loads(pid_path.read_text())["owner_fd"]
        assert Path(f"/proc/{child.pid}/fd/{inherited}").exists()
        live_peer = DurableTaskStore(sessionmaker(engine))
        try:
            live_peer.recover()
            assert live_peer.snapshot(["synthetic-crash-job"])["synthetic-crash-job"].status is TaskStatus.RUNNING
        finally:
            live_peer.close_owner(remove=True)
        parent.kill()
        parent.wait(timeout=3)
        deadline = time.monotonic() + 2
        reaped = False
        while time.monotonic() < deadline:
            pid, _ = os.waitpid(child.pid, os.WNOHANG)
            if pid == child.pid:
                reaped = True
                break
            time.sleep(0.01)
        assert reaped, "post-processing child survived owning app SIGKILL"
        assert not psutil.pid_exists(child.pid)
        restarted = DurableTaskStore(sessionmaker(engine))
        restarted.recover()
        recovered = restarted.snapshot(["synthetic-crash-job"])
        assert recovered["synthetic-crash-job"].status is TaskStatus.PENDING
        restarted.close_owner(remove=True)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=3)
        if child is not None and psutil.pid_exists(child.pid):
            child.kill()
            os.waitpid(child.pid, 0)
        assert libc.prctl(36, old.value, 0, 0, 0) == 0
        engine.dispose()
