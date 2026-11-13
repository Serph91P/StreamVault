"""#959: real owned children, event-controlled slow media boundary, real manager."""

import asyncio
from contextlib import asynccontextmanager
import sys

import pytest

from app.models import Stream, Streamer
from app.services.recording.process_manager import ProcessManager


@asynccontextmanager
async def native_recordings(*, ignoring_first=False):
    manager = ProcessManager.__new__(ProcessManager)
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    manager.monitor_interval_seconds = 10
    manager.active_processes = {}
    manager.long_stream_processes = {}
    children = []

    async def spawn(name, *, ignore_termination=False):
        program = "import sys; sys.stdin.buffer.read()"
        if ignore_termination:
            program = (
                "import signal,sys; "
                "signal.signal(signal.SIGTERM, lambda *_: print('TERM', flush=True)); "
                "print('READY', flush=True); sys.stdin.buffer.read()"
            )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            program,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE
            if ignore_termination
            else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        children.append(child)
        manager.active_processes[name] = child
        manager._track_recording_process(name, child)
        if ignore_termination:
            assert child.stdout is not None
            assert (
                await asyncio.wait_for(child.stdout.readline(), timeout=2) == b"READY\n"
            )
        return child

    first = await spawn("stream_a", ignore_termination=ignoring_first)
    second = await spawn("stream_b")
    info: dict[str, object] = {"monitor_task": None}
    manager.long_stream_processes["stream_a"] = info
    entered = asyncio.Event()
    release = asyncio.Event()
    finalized = []

    async def slow_media_boundary(segment_info):
        assert segment_info is info
        finalized.append(segment_info)
        entered.set()
        await release.wait()

    manager._finalize_segmented_recording = slow_media_boundary
    try:
        yield manager, first, second, info, entered, release, finalized, spawn
    finally:
        release.set()
        for child in children:
            if child.returncode is None:
                child.kill()
            await asyncio.wait_for(child.wait(), timeout=2)
        manager.active_processes.clear()
        manager.long_stream_processes.clear()
        await manager._get_task_supervisor().shutdown(process_timeout=1)


@pytest.mark.asyncio
@pytest.mark.parametrize("other_operation", ["stop", "registry"])
async def test_slow_segment_finalization_does_not_serialize_unrelated_channel(
    other_operation,
):
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            assert first.returncode is not None
            if other_operation == "stop":
                assert await asyncio.wait_for(
                    manager.terminate_process("stream_b"), timeout=1
                )
                assert second.returncode is not None
            else:
                # This is the same registry critical section used by start/rotation.
                await asyncio.wait_for(manager.lock.acquire(), timeout=1)
                try:
                    assert manager.active_processes["stream_b"] is second
                finally:
                    manager.lock.release()
            assert not release.is_set()
        finally:
            release.set()
            assert await stopping
        assert finalized == [info]


@pytest.mark.asyncio
async def test_slow_finalization_does_not_block_other_public_recording_start(tmp_path):
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):

        async def no_provider_token():
            return None

        async def synthetic_segment(
            stream, segment_path, quality, segment_info, **kwargs
        ):
            return await spawn(f"stream_{stream.id}")

        async def synthetic_auth_options(stream):
            return 0, True

        manager._resolve_recording_token = no_provider_token
        manager._recording_auth_options = synthetic_auth_options
        manager._start_segment = synthetic_segment
        stream = Stream(
            id=42, streamer=Streamer(id=42, username="synthetic", twitch_id=None)
        )
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            child = await asyncio.wait_for(
                manager.start_recording_process(
                    stream, str(tmp_path / "new.ts"), "best"
                ),
                timeout=1,
            )
            assert child is not None
            assert child is manager.active_processes["stream_42"]
            assert child.returncode is None
            assert (
                manager.long_stream_processes["stream_42"]["monitor_task"] is not None
            )
            assert not release.is_set()
        finally:
            release.set()
            assert await stopping


@pytest.mark.asyncio
async def test_duplicate_stop_waits_for_same_recording_finalization():
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        duplicate_started = asyncio.Event()

        async def duplicate_stop():
            duplicate_started.set()
            return await manager.terminate_process("stream_a")

        duplicate = None
        try:
            await asyncio.wait_for(entered.wait(), timeout=2)
            duplicate = asyncio.create_task(duplicate_stop())
            await duplicate_started.wait()
            assert not duplicate.done()
        finally:
            release.set()
            assert await stopping
            if duplicate is not None:
                assert await duplicate
        assert finalized == [info]


@pytest.mark.asyncio
async def test_cancelled_finalizer_releases_locks_and_does_not_report_success():
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        await asyncio.wait_for(entered.wait(), timeout=2)
        stopping.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert first.returncode is not None
        assert not manager.lock.locked()
        assert await asyncio.wait_for(manager.terminate_process("stream_b"), timeout=1)
        assert second.returncode is not None


@pytest.mark.asyncio
async def test_cancelled_child_wait_restores_owned_registry_entry():
    async with native_recordings(ignoring_first=True) as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        assert first.stdout is not None
        assert await asyncio.wait_for(first.stdout.readline(), timeout=2) == b"TERM\n"
        stopping.cancel()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        assert first.returncode is None
        assert manager.active_processes.get("stream_a") is first
        assert manager.long_stream_processes["stream_a"] is info
        assert finalized == []
        assert not manager.lock.locked()


@pytest.mark.asyncio
async def test_stop_authorization_denial_preserves_child_and_registry():
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        info.update(
            upstream_channel_key="synthetic",
            upstream_generation=1,
            upstream_process_group_id=first.pid,
            upstream_process_start_fingerprint="synthetic",
        )

        class Coordinator:
            async def assert_stop_authorized(self, **kwargs):
                raise PermissionError("stale generation")

        manager.upstream_coordinator = Coordinator()
        assert await manager.terminate_process("stream_a") is False
        assert first.returncode is None
        assert manager.active_processes["stream_a"] is first
        assert manager.long_stream_processes["stream_a"] is info
        assert finalized == []


@pytest.mark.asyncio
async def test_owner_change_during_authorization_cannot_terminate_replacement():
    async with native_recordings() as (
        manager,
        first,
        second,
        info,
        entered,
        release,
        finalized,
        spawn,
    ):
        authorizing = asyncio.Event()
        authorized = asyncio.Event()
        info.update(
            upstream_channel_key="synthetic",
            upstream_generation=1,
            upstream_process_group_id=first.pid,
            upstream_process_start_fingerprint="synthetic",
        )

        class Coordinator:
            async def assert_stop_authorized(self, **kwargs):
                authorizing.set()
                await authorized.wait()

        manager.upstream_coordinator = Coordinator()
        stopping = asyncio.create_task(manager.terminate_process("stream_a"))
        replacement = None
        try:
            await asyncio.wait_for(authorizing.wait(), timeout=2)
            await asyncio.wait_for(manager.lock.acquire(), timeout=1)
            try:
                replacement = await spawn("stream_a")
                replacement_info = {"monitor_task": None}
                manager.long_stream_processes["stream_a"] = replacement_info
            finally:
                manager.lock.release()
            authorized.set()
            assert await stopping is False
            assert first.returncode is None
            assert replacement.returncode is None
            assert manager.active_processes["stream_a"] is replacement
            assert manager.long_stream_processes["stream_a"] is replacement_info
            assert finalized == []
        finally:
            if replacement is None:
                stopping.cancel()
            authorized.set()
            await asyncio.gather(stopping, return_exceptions=True)
