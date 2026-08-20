import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.recording.process_manager import ProcessManager


class FakeProcess:
    def __init__(
        self,
        *,
        returncode: int | None = None,
        terminate_error: BaseException | None = None,
        release_on_terminate: bool = True,
        release_on_kill: bool = True,
    ) -> None:
        self.returncode = returncode
        self.terminate_error = terminate_error
        self.release_on_terminate = release_on_terminate
        self.release_on_kill = release_on_kill
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = 0
        self.wait_started = asyncio.Event()
        self.release = asyncio.Event()
        if returncode is not None:
            self.release.set()

    def terminate(self) -> None:
        self.terminate_calls += 1
        if self.terminate_error is not None:
            raise self.terminate_error
        if self.release_on_terminate:
            self.returncode = -15
            self.release.set()

    def kill(self) -> None:
        self.kill_calls += 1
        if self.release_on_kill:
            self.returncode = -9
            self.release.set()

    async def wait(self) -> int:
        self.wait_calls += 1
        self.wait_started.set()
        await self.release.wait()
        assert self.returncode is not None
        return self.returncode


def make_manager(process: FakeProcess, stream_id: int = 7) -> ProcessManager:
    manager = object.__new__(ProcessManager)
    manager.active_processes = {f"stream_{stream_id}": process}
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    return manager


def make_segment_info() -> dict:
    return {
        "base_output_path": "/tmp/recording.ts",
        "segment_dir": "/tmp/recording_segments",
        "current_segment_path": "/tmp/recording_segments/recording_part001.ts",
        "segment_count": 1,
        "segment_start_time": datetime(2026, 1, 1),
        "total_segments": [],
    }


def install_segment_starter(
    manager: ProcessManager,
    started: list[FakeProcess],
) -> None:
    async def start_segment(stream, segment_path, quality, segment_info):
        replacement = FakeProcess()
        manager.active_processes[f"stream_{stream.id}"] = replacement
        started.append(replacement)
        return replacement

    manager._start_segment = start_segment


@pytest.mark.asyncio
async def test_rotation_reaps_exited_process_before_starting_replacement() -> None:
    old_process = FakeProcess(returncode=0)
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)

    rotated = await manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")

    assert rotated is True
    assert old_process.wait_calls == 1
    assert old_process.terminate_calls == 0
    assert old_process.kill_calls == 0
    assert manager.active_processes["stream_7"] is started[0]


@pytest.mark.asyncio
async def test_rotation_terminates_and_waits_before_starting_replacement() -> None:
    old_process = FakeProcess()
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)

    rotated = await manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")

    assert rotated is True
    assert old_process.terminate_calls == 1
    assert old_process.wait_calls == 1
    assert old_process.kill_calls == 0
    assert len(started) == 1


@pytest.mark.asyncio
async def test_rotation_kills_and_waits_after_graceful_timeout(monkeypatch) -> None:
    old_process = FakeProcess(release_on_terminate=False)
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)
    monkeypatch.setattr(
        "app.services.recording.process_manager.ASYNC_DELAYS",
        SimpleNamespace(RECORDING_ERROR_RECOVERY=0.01),
    )

    rotated = await manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")

    assert rotated is True
    assert old_process.terminate_calls == 1
    assert old_process.kill_calls == 1
    assert old_process.wait_calls == 2
    assert len(started) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "termination_error",
    [ProcessLookupError(), PermissionError()],
)
async def test_rotation_retains_tracking_when_terminate_raises(
    termination_error: BaseException,
) -> None:
    old_process = FakeProcess(terminate_error=termination_error)
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    original_path = segment_info["current_segment_path"]
    started = []
    install_segment_starter(manager, started)

    rotated = await manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")

    assert rotated is False
    assert manager.active_processes["stream_7"] is old_process
    assert segment_info["current_segment_path"] == original_path
    assert started == []


@pytest.mark.asyncio
async def test_rotation_retains_tracking_when_forced_wait_times_out(
    monkeypatch,
) -> None:
    old_process = FakeProcess(
        release_on_terminate=False,
        release_on_kill=False,
    )
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)
    monkeypatch.setattr(
        "app.services.recording.process_manager.ASYNC_DELAYS",
        SimpleNamespace(RECORDING_ERROR_RECOVERY=0.01),
    )

    rotated = await manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")

    assert rotated is False
    assert manager.active_processes["stream_7"] is old_process
    assert old_process.kill_calls == 1
    assert started == []


@pytest.mark.asyncio
async def test_rotation_cancellation_retains_tracking() -> None:
    old_process = FakeProcess(release_on_terminate=False)
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)

    rotation = asyncio.create_task(
        manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")
    )
    await old_process.wait_started.wait()
    rotation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await rotation
    assert manager.active_processes["stream_7"] is old_process
    assert started == []


@pytest.mark.asyncio
async def test_rotation_does_not_replace_newer_tracked_process() -> None:
    old_process = FakeProcess(release_on_terminate=False)
    newer_process = FakeProcess()
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)

    rotation = asyncio.create_task(
        manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")
    )
    await old_process.wait_started.wait()
    manager.active_processes["stream_7"] = newer_process
    old_process.returncode = -15
    old_process.release.set()

    assert await rotation is False
    assert manager.active_processes["stream_7"] is newer_process
    assert started == []


@pytest.mark.asyncio
async def test_concurrent_rotation_requests_start_one_replacement() -> None:
    old_process = FakeProcess(release_on_terminate=False)
    manager = make_manager(old_process)
    first_segment_info = make_segment_info()
    second_segment_info = make_segment_info()
    started = []
    install_segment_starter(manager, started)

    first_rotation = asyncio.create_task(
        manager._rotate_segment(SimpleNamespace(id=7), first_segment_info, "best")
    )
    await old_process.wait_started.wait()
    second_rotation = asyncio.create_task(
        manager._rotate_segment(SimpleNamespace(id=7), second_segment_info, "best")
    )
    await asyncio.sleep(0)
    old_process.returncode = -15
    old_process.release.set()

    results = await asyncio.gather(first_rotation, second_rotation)
    assert results == [True, False]
    assert old_process.terminate_calls == 1
    assert len(started) == 1
    assert manager.active_processes["stream_7"] is started[0]
