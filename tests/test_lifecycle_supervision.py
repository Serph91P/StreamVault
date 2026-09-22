import asyncio
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


def test_production_lifespan_has_no_schema_creation_or_startup_delay():
    import inspect

    from app.lifespan import lifespan

    source = inspect.getsource(lifespan)
    assert "metadata.create_all" not in source
    assert "BRIEF_PAUSE" not in source
