"""Capture stop is independent of saturated post-processing, including SIGKILL."""

import asyncio
import json
import os
import signal
from contextlib import AsyncExitStack
from pathlib import Path

import pytest

from app.models import Stream
from app.services.recording.process_manager import ProcessManager
from app.utils.media_process import media_process
from test_recording_completion_notifications import (
    CompletedChild,
    completion_state,
    make_manager,
    make_orchestrator,
)


async def capture(path):
    return await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-re",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=5",
        "-t",
        "30",
        "-c:v",
        "mpeg2video",
        "-threads",
        "1",
        "-flush_packets",
        "1",
        "-f",
        "mpegts",
        str(path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )


async def wait_until(predicate, timeout=4):
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
@pytest.mark.parametrize("kill", [False, True], ids=["sigterm", "timeout-sigkill"])
@pytest.mark.parametrize("cancel", [False, True], ids=["complete", "cancel-recover"])
async def test_saturated_finalization_does_not_block_peer_capture_stop(
    completion_state, monkeypatch, kill, cancel
):
    state = completion_state
    # Disable notification transport, not the real finalization/DB/file path.
    from app.models import GlobalSettings

    with state.sessions() as db:
        db.query(GlobalSettings).first().notifications_enabled = False
        db.commit()
    segment_dir = state.root / "capture_segments"
    segment_dir.mkdir()
    segment = segment_dir / "capture_part001.ts"
    peer_path = state.root / "peer.ts"
    manager = ProcessManager.__new__(ProcessManager)
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    manager.active_processes = {}
    manager.long_stream_processes = {}
    admissions = []

    async def accepted(recording_id, path):
        assert not manager.lock.locked()
        assert Path(path).stat().st_size > 0
        admissions.append((recording_id, path))

    manager.post_processing_callback = accepted
    children, jobs = [], []
    try:
        async with AsyncExitStack() as stack:
            holders = []
            for _ in range(2):
                holder, _output = await stack.enter_async_context(
                    media_process(
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-re",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=160x90:rate=5",
                        "-t",
                        "30",
                        "-threads",
                        "1",
                        "-f",
                        "null",
                        "-",
                    )
                )
                holders.append(holder)
            first = await capture(segment)
            second = await capture(peer_path)
            children.extend((first, second))
            await wait_until(
                lambda: all(
                    p.exists() and p.stat().st_size for p in (segment, peer_path)
                )
            )
            assert all(child.returncode is None for child in children + holders)
            info = {
                "stream_id": state.stream_id,
                "recording_id": 1045,
                "monitor_task": None,
                "segment_dir": str(segment_dir),
                "total_segments": [{"path": str(segment)}],
                "base_output_path": str(state.root / "capture.ts"),
            }
            key = f"stream_{state.stream_id}"
            manager.active_processes = {key: first, "peer": second}
            manager.long_stream_processes[key] = info
            monitor_ready = asyncio.Event()
            collect = manager._collect_streamlink_output

            async def observe_collection(process):
                monitor_ready.set()
                return await collect(process)

            monkeypatch.setattr(
                manager, "_collect_streamlink_output", observe_collection
            )
            monitor = asyncio.create_task(manager.monitor_process(first))
            jobs.append(monitor)
            # Observe the real monitor after its owner snapshot, not a timed guess.
            await asyncio.wait_for(monitor_ready.wait(), timeout=3)
            if kill:
                # A stopped real FFmpeg cannot handle SIGTERM; the normal stop
                # deadline must escalate to SIGKILL, without a fake wait/child.
                os.kill(first.pid, signal.SIGSTOP)
            stop = asyncio.create_task(manager.terminate_process(key, timeout=1))
            jobs.append(stop)
            await wait_until(lambda: first.returncode is not None, timeout=3)
            await wait_until(lambda: (segment_dir / "concat_list.txt").exists())
            peer = asyncio.create_task(manager.terminate_process("peer", timeout=1))
            jobs.append(peer)
            await asyncio.wait_for(asyncio.shield(peer), timeout=2)
            assert second.returncode is not None
            assert not stop.done()  # Both heavy slots remain occupied.
            assert all(holder.returncode is None for holder in holders)
            assert not manager.lock.locked()
            assert admissions == []
            assert manager.long_stream_processes[key] is info
            duplicate = asyncio.create_task(manager.terminate_process(key, timeout=1))
            jobs.append(duplicate)
            assert (
                await manager._rotate_segment(Stream(id=state.stream_id), info, "best")
                is False
            )
            await asyncio.sleep(
                0
            )  # Give duplicate stop a turn to enter the owned lock.
            assert not duplicate.done()
            assert not monitor.done()
            if cancel:
                stop.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await stop
                assert segment.stat().st_size > 0
                assert admissions == []
                assert manager.long_stream_processes == {}
        if cancel:
            # Restart/recovery can use the intact on-disk inputs; no orphan task
            # from the cancelled stop is allowed to publish a second file.
            recovered = ProcessManager.__new__(ProcessManager)
            recovered.post_processing_callback = accepted
            await asyncio.wait_for(
                recovered._finalize_segmented_recording(info), timeout=5
            )
        else:
            assert await asyncio.wait_for(stop, timeout=5) is True
        assert await duplicate is True
        await monitor
        assert len(admissions) == 1
        assert admissions[0][0] == 1045
        final = Path(admissions[0][1])
        assert final == state.root / "capture.ts"
        assert manager.active_processes == manager.long_stream_processes == {}
        assert not segment.exists()
        async with media_process(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(final),
        ) as (probe, output):
            stdout, _stderr = await output.wait()
        assert probe.returncode == 0
        assert float(json.loads(stdout)["format"]["duration"]) > 0
        async with media_process(
            "ffmpeg",
            "-v",
            "error",
            "-xerror",
            "-i",
            str(final),
            "-threads",
            "1",
            "-f",
            "null",
            "-",
        ) as (decode, output):
            await output.wait()
        assert decode.returncode == 0
    finally:
        for job in jobs:
            if not job.done():
                job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()


@pytest.mark.asyncio
async def test_cancel_before_reap_retains_exact_live_owner(completion_state):
    entered = asyncio.Event()

    class LiveChild(CompletedChild):
        def __init__(self):
            super().__init__()
            self.returncode = None

        async def wait(self):
            entered.set()
            await asyncio.Event().wait()

    child = LiveChild()
    manager = make_manager(completion_state, child)
    key = f"stream_{completion_state.stream_id}"
    info = {"monitor_task": None}
    manager.long_stream_processes[key] = info
    stop = asyncio.create_task(manager.terminate_process(key))
    await entered.wait()
    stop.cancel()
    with pytest.raises(asyncio.CancelledError):
        await stop
    assert manager.active_processes == {key: child}
    assert manager.long_stream_processes == {key: info}
    assert not manager.lock.locked()
    assert not manager.rotation_locks[key].locked()


@pytest.mark.asyncio
async def test_callback_admission_failure_preserves_final_path_for_restart_retry(
    completion_state, monkeypatch
):
    from datetime import datetime, timezone
    from app.models import Recording
    from app.services.recording.recording_orchestrator import RecordingOrchestrator

    state = completion_state
    final = state.root / "capture.ts"
    final.write_bytes(b"completed media stays available after admission failure")
    with state.sessions() as db:
        recording = Recording(
            stream_id=state.stream_id,
            status="recording",
            path=str(state.root / "old_segment.ts"),
            start_time=datetime.now(timezone.utc),
        )
        db.add(recording)
        db.commit()
        identifier = recording.id
        db.close()
        orchestrator = make_orchestrator(state)

        async def unavailable(*args):
            raise OSError("synthetic admission failure")

        monkeypatch.setattr(
            orchestrator.post_processing_coordinator,
            "enqueue_post_processing",
            unavailable,
        )
        await orchestrator.process_manager._trigger_post_processing_for_segmented_recording(
            {
                "stream_id": state.stream_id,
                "recording_id": identifier,
                "base_output_path": str(state.root / "old_segment.ts"),
                "final_output_path": str(final),
            }
        )
        assert (
            identifier not in orchestrator.lifecycle_manager._postprocessing_scheduled
        )
    # A fresh session/orchestrator sees the settled final file, not deleted inputs.
    with state.sessions() as db:
        persisted = db.get(Recording, identifier)
        assert persisted.path == str(final)
        assert persisted.status == "completed"
        db.close()
        recovered = make_orchestrator(state)
        admitted = []

        async def accepted(*args):
            admitted.append(args)
            return True

        monkeypatch.setattr(
            recovered.post_processing_coordinator, "enqueue_post_processing", accepted
        )
        await recovered.process_manager.post_processing_callback(
            identifier, persisted.path
        )
        assert len(admitted) == 1
        assert admitted[0][:2] == (identifier, str(final))
        assert identifier in recovered.lifecycle_manager._postprocessing_scheduled
    assert (
        final.read_bytes() == b"completed media stays available after admission failure"
    )


@pytest.mark.asyncio
async def test_failed_finalizer_keeps_input_and_does_not_remove_replacement_owner(
    completion_state,
):
    state = completion_state
    child = CompletedChild()
    manager = make_manager(state, child)
    key = f"stream_{state.stream_id}"
    segment = state.root / "capture_part001.ts"
    segment.write_bytes(b"owned input preserved for recovery")
    info = {"monitor_task": None, "segment_dir": str(state.root)}
    manager.long_stream_processes[key] = info
    replacement = {"monitor_task": None}

    async def failed_finalizer(owned):
        assert owned is info
        assert not manager.lock.locked()
        manager.long_stream_processes[key] = replacement
        raise OSError("synthetic finalizer failure")

    manager._finalize_segmented_recording = failed_finalizer
    assert await manager.terminate_process(key) is False
    assert segment.read_bytes() == b"owned input preserved for recovery"
    assert manager.long_stream_processes[key] is replacement
    assert not manager.rotation_locks[key].locked()
