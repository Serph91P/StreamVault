import asyncio
from types import SimpleNamespace
from typing import cast

import pytest


@pytest.mark.asyncio
async def test_supervisor_names_tracks_and_cancels_tasks_in_reverse_order():
    from app.services.system.supervisor import TaskSupervisor

    cancelled = []
    started = [asyncio.Event(), asyncio.Event()]

    async def worker(name, ready):
        ready.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.append(name)

    supervisor = TaskSupervisor("test")
    first = supervisor.create_task("first", worker("first", started[0]))
    second = supervisor.create_task("second", worker("second", started[1]))
    await asyncio.gather(*(event.wait() for event in started))

    assert first.get_name() == "streamvault:test:first"
    assert second.get_name() == "streamvault:test:second"
    assert supervisor.task_names == ("first", "second")

    await supervisor.shutdown()
    await supervisor.shutdown()

    assert cancelled == ["second", "first"]
    assert first.done() and second.done()
    assert supervisor.closed is True
    assert supervisor.task_names == ()


@pytest.mark.asyncio
async def test_supervisor_observes_background_failure_without_leaking_diagnostics():
    from app.services.system.supervisor import TaskSupervisor

    async def fail():
        raise RuntimeError("token=synthetic-secret")

    supervisor = TaskSupervisor("test")
    task = supervisor.create_task("failure", fail())
    await asyncio.sleep(0)

    assert task.done()
    assert supervisor.failures == (("failure", "RuntimeError"),)
    await supervisor.shutdown()


@pytest.mark.asyncio
async def test_supervisor_reaps_tracked_process_and_is_idempotent():
    from app.services.system.supervisor import TaskSupervisor

    process = await asyncio.create_subprocess_exec(
        "python3",
        "-c",
        "import time; time.sleep(30)",
    )
    supervisor = TaskSupervisor("test")
    supervisor.track_process("synthetic", process)

    await supervisor.shutdown()
    await supervisor.shutdown()

    assert process.returncode is not None
    assert supervisor.process_names == ()


@pytest.mark.asyncio
async def test_supervisor_rejects_duplicate_and_post_shutdown_tasks():
    from app.services.system.supervisor import TaskSupervisor

    started = asyncio.Event()

    async def worker():
        started.set()
        await asyncio.Future()

    supervisor = TaskSupervisor("test")
    supervisor.create_task("worker", worker())
    await started.wait()

    duplicate = worker()
    with pytest.raises(RuntimeError, match="task already running"):
        supervisor.create_task("worker", duplicate)
    assert duplicate.cr_frame is None

    await supervisor.shutdown()

    late = worker()
    with pytest.raises(RuntimeError, match="supervisor is shutting down"):
        supervisor.create_task("late", late)
    assert late.cr_frame is None


@pytest.mark.asyncio
async def test_supervisor_releases_completed_process():
    from app.services.system.supervisor import TaskSupervisor

    process = await asyncio.create_subprocess_exec("python3", "-c", "pass")
    supervisor = TaskSupervisor("test")
    supervisor.track_process("synthetic", process)

    await supervisor.release_process("synthetic")
    await supervisor.release_process("missing")

    assert process.returncode == 0
    assert supervisor.process_names == ()


@pytest.mark.asyncio
async def test_supervisor_kills_process_that_ignores_terminate():
    from app.services.system.supervisor import TaskSupervisor

    class StubbornProcess:
        returncode = None

        def __init__(self):
            self.terminated = False
            self.killed = False
            self._reaped = asyncio.Event()

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.returncode = -9
            self._reaped.set()

        async def wait(self):
            await self._reaped.wait()
            return self.returncode

    process = StubbornProcess()
    supervisor = TaskSupervisor("test")
    supervisor.track_process("stubborn", cast(asyncio.subprocess.Process, process))

    await supervisor.shutdown(process_timeout=0)

    assert process.terminated is True
    assert process.killed is True
    assert process.returncode == -9
    assert supervisor.process_names == ()


@pytest.mark.asyncio
async def test_supervisor_retains_identity_fenced_process_when_custom_reaper_refuses():
    from app.services.system.supervisor import TaskSupervisor

    class Process:
        returncode = None

        def terminate(self):
            raise AssertionError("generic termination bypassed the identity fence")

    reaper_calls = []

    async def fenced_reaper(timeout):
        reaper_calls.append(timeout)
        return False

    supervisor = TaskSupervisor("test")
    supervisor.track_process(
        "fenced",
        cast(asyncio.subprocess.Process, Process()),
        reaper=fenced_reaper,
    )

    await supervisor.shutdown(process_timeout=0.25)

    assert reaper_calls == [0.25]
    assert supervisor.process_names == ("fenced",)


def test_supervisor_rejects_duplicate_and_post_shutdown_processes():
    from app.services.system.supervisor import TaskSupervisor

    running = type("Process", (), {"returncode": None})()
    replacement = type("Process", (), {"returncode": None})()
    supervisor = TaskSupervisor("test")
    supervisor.track_process("process", cast(asyncio.subprocess.Process, running))

    with pytest.raises(RuntimeError, match="process already running"):
        supervisor.track_process(
            "process", cast(asyncio.subprocess.Process, replacement)
        )

    supervisor._shutting_down = True
    with pytest.raises(RuntimeError, match="supervisor is shutting down"):
        supervisor.track_process("late", cast(asyncio.subprocess.Process, replacement))


@pytest.mark.asyncio
async def test_lifecycle_shutdown_helpers_support_registry_variants_and_failures():
    from app.lifespan import _shutdown_step, _stop_event_registry

    calls = []

    async def record(name):
        calls.append(name)

    await _stop_event_registry(
        type(
            "Registry",
            (),
            {"eventsub": type("EventSub", (), {"stop": lambda self: record("stop")})()},
        )()
    )
    await _stop_event_registry(
        type("Registry", (), {"cleanup": lambda self: record("cleanup")})()
    )

    async def fail():
        raise RuntimeError("synthetic diagnostic must not escape")

    await _shutdown_step("synthetic", fail)

    assert calls == ["stop", "cleanup"]


@pytest.mark.asyncio
async def test_live_service_can_restart_with_a_new_supervisor_generation(tmp_path):
    from app.services.live_streaming_service import LiveStreamingService

    service = LiveStreamingService(output_root=tmp_path)

    await service.start()
    first_generation = service._supervisor
    await service.stop()
    await service.start()
    second_generation = service._supervisor
    await service.stop()

    assert first_generation.closed is True
    assert second_generation.closed is True
    assert second_generation is not first_generation


@pytest.mark.asyncio
async def test_live_processes_are_supervisor_owned_until_fenced_shutdown(
    monkeypatch, tmp_path
):
    import app.services.live_streaming_service as live_module
    from app.services.live_streaming_service import LiveStreamingService

    releases = []

    class Coordinator:
        async def reserve(self, **values):
            return SimpleNamespace(
                channel_key=values["channel_key"],
                generation=7,
                live_session_id=values["live_session_id"],
            )

        async def inspect_process_identity(self, pid):
            return SimpleNamespace(
                pid=pid,
                process_group_id=pid,
                started_at=1.0,
                fingerprint=f"identity-{pid}",
            )

        async def activate(self, **values):
            return SimpleNamespace(
                process_group_id=values["process_group_id"],
                process_started_at=values["process_started_at"],
                process_start_fingerprint=values["process_start_fingerprint"],
            )

        async def assert_stop_authorized(self, **_values):
            return None

        async def release(self, **values):
            releases.append((values["generation"], values["reason"]))
            return True

    class Process:
        def __init__(self, pid):
            self.pid = pid
            self.returncode: int | None = None
            self.stdin = SimpleNamespace()
            self.stdout = SimpleNamespace()
            self.stderr = SimpleNamespace()

        async def wait(self):
            assert self.returncode is not None
            return self.returncode

    processes = [Process(4101), Process(4102)]

    async def create_process(*_args, **_kwargs):
        return processes.pop(0)

    async def streamlink_command(*_args, **_kwargs):
        return ["streamlink", "synthetic"]

    async def idle(*_args, **_kwargs):
        await asyncio.Future()

    process_by_group = {process.pid: process for process in processes}

    def terminate_group(process_group_id, _signal):
        process_by_group[process_group_id].returncode = -15

    monkeypatch.setattr(live_module.asyncio, "create_subprocess_exec", create_process)
    monkeypatch.setattr(live_module.os, "killpg", terminate_group)

    service = LiveStreamingService(coordinator=Coordinator(), output_root=tmp_path)
    monkeypatch.setattr(service, "_build_streamlink_command", streamlink_command)
    monkeypatch.setattr(service, "_build_ffmpeg_command", lambda _path: ["ffmpeg"])
    monkeypatch.setattr(
        service, "_wait_for_playlist", lambda *_args, **_kwargs: _true()
    )
    monkeypatch.setattr(service, "_log_stderr", idle)
    monkeypatch.setattr(service, "_pipe_streamlink_to_ffmpeg", idle)
    monkeypatch.setattr(service, "_monitor_session", idle)

    result = await service.start_stream("synthetic-channel")

    assert service._supervisor.process_names == (
        f"{result.session_id}:ffmpeg",
        f"{result.session_id}:streamlink",
    )

    await service.stop()

    assert service._supervisor.process_names == ()
    assert service.sessions == {}
    assert releases == [(7, "live_stopped")]


@pytest.mark.asyncio
async def test_recording_shutdown_reaps_supervised_pid_and_releases_lease(monkeypatch):
    from importlib import import_module

    process_manager_module = import_module("app.services.recording.process_manager")
    from app.services.recording.process_manager import ProcessManager
    from app.services.system.supervisor import TaskSupervisor

    calls = []

    class Coordinator:
        async def assert_stop_authorized(self, **values):
            calls.append(("authorized", values["process_pid"]))

        async def inspect_process_identity(self, pid):
            return SimpleNamespace(
                pid=pid,
                process_group_id=pid,
                fingerprint=f"identity-{pid}",
            )

        async def release(self, **values):
            calls.append(("released", values["generation"], values["reason"]))
            return True

    class Process:
        pid = 4201
        returncode: int | None = None

        async def wait(self):
            assert self.returncode is not None
            return self.returncode

    process = Process()
    process_id = "stream_7"
    tracked_segment_info = {
        "upstream_channel_key": "synthetic-channel",
        "upstream_generation": 3,
        "upstream_activated": True,
        "upstream_process_group_id": process.pid,
        "upstream_process_start_fingerprint": f"identity-{process.pid}",
        "monitor_task": None,
    }
    manager = object.__new__(ProcessManager)
    manager.lock = asyncio.Lock()
    manager.active_processes = {process_id: process}
    manager.long_stream_processes = {process_id: tracked_segment_info}
    manager._streamlink_output_secrets = {}
    manager._segment_completion_tasks = {}
    manager._supervised_process_names = {}
    manager._task_supervisor = TaskSupervisor("recording-test")
    manager.upstream_coordinator = Coordinator()
    manager._is_shutting_down = False

    async def finalize(segment_info):
        assert segment_info is tracked_segment_info

    manager._finalize_segmented_recording = finalize

    def terminate_group(process_group_id, _signal):
        assert process_group_id == process.pid
        process.returncode = -15

    monkeypatch.setattr(process_manager_module.os, "killpg", terminate_group)
    manager._track_recording_process(process_id, process)

    await manager.graceful_shutdown(timeout=1)

    assert manager.active_processes == {}
    assert manager.long_stream_processes == {}
    assert manager._task_supervisor.process_names == ()
    assert manager._supervised_process_names == {}
    assert calls == [
        ("authorized", process.pid),
        ("released", 3, "recording_stopped"),
    ]


async def _true():
    return True


def test_production_lifespan_has_no_schema_creation_or_startup_delay():
    import inspect

    from app.lifespan import lifespan

    source = inspect.getsource(lifespan)
    assert "metadata.create_all" not in source
    assert "BRIEF_PAUSE" not in source
