import asyncio
import importlib
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.recording.process_manager import ProcessManager
from app.services.recording.exceptions import ProcessError


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
        self.communicate_calls = 0
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

    async def communicate(self) -> tuple[bytes, bytes]:
        self.communicate_calls += 1
        return b"", b"harmless local failure"


def make_manager(process: FakeProcess, stream_id: int = 7) -> ProcessManager:
    manager = object.__new__(ProcessManager)
    manager.active_processes = {f"stream_{stream_id}": process}
    manager.long_stream_processes = {}
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    return manager


def make_segment_info() -> dict:
    return {
        "stream_id": 7,
        "base_output_path": "/tmp/recording.ts",
        "segment_dir": "/tmp/recording_segments",
        "current_segment_path": "/tmp/recording_segments/recording_part001.ts",
        "segment_count": 1,
        "segment_start_time": datetime(2026, 1, 1),
        "total_segments": [],
        "monitor_task": None,
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


def install_immediate_exit_start(
    monkeypatch,
    failed_process: FakeProcess,
) -> tuple[ProcessManager, SimpleNamespace, list]:
    process_manager_module = importlib.import_module(
        "app.services.recording.process_manager"
    )
    manager = object.__new__(ProcessManager)
    manager.active_processes = {}
    manager.long_stream_processes = {}
    manager.lock = asyncio.Lock()
    manager.rotation_locks = {}
    manager.logging_service = None
    monitor_coroutines = []

    class FakeQuery:
        def first(self):
            return None

        def filter(self, *args):
            return self

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query(self, *args):
            return FakeQuery()

    class FakeTokenService:
        def __init__(self, db):
            pass

        async def get_valid_access_token(self):
            return None

    async def create_subprocess(*args, **kwargs):
        return failed_process

    def create_task(coroutine):
        monitor_coroutines.append(coroutine)
        coroutine.close()
        return SimpleNamespace()

    monkeypatch.setattr("app.database.SessionLocal", FakeSession)
    monkeypatch.setattr(
        "app.services.system.twitch_token_service.TwitchTokenService",
        FakeTokenService,
    )
    monkeypatch.setattr(
        process_manager_module,
        "get_streamlink_command",
        lambda **kwargs: ["harmless-local-command"],
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    monkeypatch.setattr(asyncio, "create_task", create_task)
    monkeypatch.setattr(
        process_manager_module,
        "ASYNC_DELAYS",
        SimpleNamespace(PROCESS_START_GRACE=0),
    )
    stream = SimpleNamespace(
        id=7,
        streamer_id=3,
        streamer=SimpleNamespace(username="local-test"),
        title="",
        category_name="",
    )
    return manager, stream, monitor_coroutines


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


@pytest.mark.asyncio
async def test_monitor_finalization_and_rotation_cannot_both_win() -> None:
    old_process = FakeProcess(returncode=0)
    manager = make_manager(old_process)
    segment_info = make_segment_info()
    manager.long_stream_processes["stream_7"] = segment_info
    started = []
    install_segment_starter(manager, started)
    finalization_started = asyncio.Event()
    release_finalization = asyncio.Event()

    async def finalize_segmented_recording(info):
        assert info is segment_info
        finalization_started.set()
        await release_finalization.wait()

    manager._finalize_segmented_recording = finalize_segmented_recording
    monitor = asyncio.create_task(manager.monitor_process(old_process))
    await finalization_started.wait()
    rotation = asyncio.create_task(
        manager._rotate_segment(SimpleNamespace(id=7), segment_info, "best")
    )

    try:
        rotated_while_finalizing = await asyncio.wait_for(
            asyncio.shield(rotation), timeout=0.05
        )
    except TimeoutError:
        rotated_while_finalizing = None
    owner_while_finalizing = manager.active_processes.get("stream_7")
    release_finalization.set()
    monitor_result, rotation_result = await asyncio.gather(monitor, rotation)

    assert (
        rotated_while_finalizing is not True and owner_while_finalizing not in started
    ), (
        "rotation and finalization both won: "
        f"rotation={rotated_while_finalizing!r}, "
        f"replacement_owned={owner_while_finalizing in started}"
    )
    assert monitor_result == 0
    assert rotation_result is False
    assert started == []


@pytest.mark.asyncio
async def test_rotation_cancellation_tracks_or_reaps_created_replacement(
    monkeypatch,
) -> None:
    process_manager_module = importlib.import_module(
        "app.services.recording.process_manager"
    )
    old_process = FakeProcess(returncode=0)
    manager = make_manager(old_process)
    manager.logging_service = None
    segment_info = make_segment_info()
    replacement = FakeProcess()
    replacement.pid = 1234
    child_created = asyncio.Event()

    class FakeQuery:
        def first(self):
            return None

        def filter(self, *args):
            return self

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query(self, *args):
            return FakeQuery()

    class FakeTokenService:
        def __init__(self, db):
            pass

        async def get_valid_access_token(self):
            return None

    async def create_subprocess(*args, **kwargs):
        child_created.set()
        return replacement

    monkeypatch.setattr("app.database.SessionLocal", FakeSession)
    monkeypatch.setattr(
        "app.services.system.twitch_token_service.TwitchTokenService",
        FakeTokenService,
    )
    monkeypatch.setattr(
        process_manager_module,
        "get_streamlink_command",
        lambda **kwargs: ["harmless-local-command"],
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_subprocess)
    monkeypatch.setattr(
        process_manager_module,
        "ASYNC_DELAYS",
        SimpleNamespace(PROCESS_START_GRACE=3600, RECORDING_ERROR_RECOVERY=1),
    )
    stream = SimpleNamespace(
        id=7,
        streamer_id=3,
        streamer=SimpleNamespace(username="local-test"),
        title="",
        category_name="",
    )

    rotation = asyncio.create_task(
        manager._rotate_segment(stream, segment_info, "best")
    )
    await child_created.wait()
    rotation.cancel()

    with pytest.raises(asyncio.CancelledError):
        await rotation

    tracked = manager.active_processes.get("stream_7") is replacement
    reaped = replacement.returncode is not None and replacement.wait_calls > 0
    assert manager.active_processes.get("stream_7") is not old_process
    assert tracked or reaped, (
        f"created replacement was orphaned: tracked={tracked}, reaped={reaped}"
    )


@pytest.mark.asyncio
async def test_start_recording_cleans_up_immediately_exited_child(
    monkeypatch,
    tmp_path,
) -> None:
    failed_process = FakeProcess(returncode=1)
    failed_process.pid = 1234
    manager, stream, monitor_coroutines = install_immediate_exit_start(
        monkeypatch,
        failed_process,
    )

    with pytest.raises(ProcessError):
        await manager.start_recording_process(
            stream,
            str(tmp_path / "recording.ts"),
            "best",
        )

    assert failed_process.communicate_calls == 1
    assert (manager.active_processes, manager.long_stream_processes) == ({}, {})
    assert monitor_coroutines == []


@pytest.mark.asyncio
async def test_immediate_exit_cleanup_preserves_newer_owners(
    monkeypatch,
    tmp_path,
) -> None:
    failed_process = FakeProcess(returncode=1)
    failed_process.pid = 1234
    manager, stream, monitor_coroutines = install_immediate_exit_start(
        monkeypatch,
        failed_process,
    )
    newer_process = FakeProcess()
    newer_segment_info = {"attempt": "newer"}

    class ReplacingLock:
        def __init__(self):
            self.enter_calls = 0

        async def __aenter__(self):
            self.enter_calls += 1
            if self.enter_calls == 2:
                manager.active_processes["stream_7"] = newer_process
                manager.long_stream_processes["stream_7"] = newer_segment_info

        async def __aexit__(self, *args):
            return None

    manager.lock = ReplacingLock()

    with pytest.raises(ProcessError):
        await manager.start_recording_process(
            stream,
            str(tmp_path / "recording.ts"),
            "best",
        )

    assert manager.active_processes["stream_7"] is newer_process
    assert manager.long_stream_processes["stream_7"] is newer_segment_info
    assert failed_process.communicate_calls == 1
    assert monitor_coroutines == []
