"""Recording actors must not inherit another factory's process/task registries."""

import asyncio
import sys
from time import monotonic

import pytest

from app.services.core.state_persistence_service import StatePersistenceService
from app.services.recording.config_manager import ConfigManager
from app.services.recording.process_manager import ProcessManager
from app.services.recording.recording_state_manager import RecordingStateManager
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator


@pytest.mark.asyncio
async def test_owned_recording_actors_stop_only_their_children_and_tasks():
    def no_sessions():
        raise AssertionError(
            "actor construction and child cleanup must not open SQL sessions"
        )

    deliveries = []

    async def first_callback(recording_id, path):
        deliveries.append(("first", recording_id, path))

    async def second_callback(recording_id, path):
        deliveries.append(("second", recording_id, path))

    legacy_process = ProcessManager()
    legacy_state = RecordingStateManager()
    legacy_config = legacy_process.config_manager
    legacy_state_config = legacy_state.config_manager
    legacy_callback = legacy_process.post_processing_callback
    managers, states, children, tasks = [], [], [], []
    try:
        for callback in (first_callback, second_callback):
            config = ConfigManager(session_factory=no_sessions)
            persistence = StatePersistenceService(session_factory=no_sessions)
            coordinator = TwitchUpstreamCoordinator(
                no_sessions, monotonic_clock=monotonic
            )
            manager = ProcessManager.for_application(
                config_manager=config,
                post_processing_callback=callback,
                upstream_coordinator=coordinator,
            )
            managers.append(manager)
            states.append(RecordingStateManager.for_application(config, persistence))
            assert manager.config_manager is config
            assert manager.upstream_coordinator is coordinator
        assert managers[0] is not managers[1] and legacy_process not in managers
        assert states[0] is not states[1] and legacy_state not in states
        assert managers[0]._task_supervisor is not managers[1]._task_supervisor
        assert legacy_process.config_manager is legacy_config
        assert legacy_process.post_processing_callback is legacy_callback
        assert legacy_state.config_manager is legacy_state_config
        assert ProcessManager() is legacy_process
        assert RecordingStateManager() is legacy_state

        for index, (manager, state) in enumerate(zip(managers, states, strict=True)):
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                "import time; time.sleep(60)",
                start_new_session=True,
            )
            children.append(child)
            manager.active_processes["same-key"] = child
            manager._track_recording_process("same-key", child)
            ready = asyncio.Event()

            async def recording_task(ready=ready):
                ready.set()
                await asyncio.Event().wait()

            task = asyncio.create_task(recording_task())
            tasks.append(task)
            await ready.wait()
            state.add_active_recording(1, {"owner": index})
            state.add_recording_task(1, task)
            await manager.post_processing_callback(1, str(index))
        assert deliveries == [("first", 1, "0"), ("second", 1, "1")]
        assert states[0].get_active_recording(1)["owner"] == 0
        assert states[1].get_active_recording(1)["owner"] == 1
        await managers[0].cleanup_all()
        states[0].cancel_all_tasks()
        await asyncio.gather(tasks[0], return_exceptions=True)
        assert children[0].returncode is not None
        assert children[1].returncode is None
        assert tasks[0].cancelled() and not tasks[1].done()
        assert managers[1].active_processes["same-key"] is children[1]
        await managers[1].cleanup_all()
        assert children[1].returncode is not None
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for manager in managers:
            await manager.cleanup_all()
        for child in children:
            if child.returncode is None:
                child.kill()
            await child.wait()
