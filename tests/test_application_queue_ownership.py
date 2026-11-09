"""Factory-local in-memory queues do not borrow the legacy singleton state."""

import asyncio

import pytest

from app.database import Base, DatabaseLifecycle
from app.main import create_app
from app.services.background_queue_service import BackgroundQueueService


@pytest.mark.asyncio
async def test_factory_queue_handlers_workers_and_metadata_are_independent(tmp_path) -> None:
    legacy_instance = BackgroundQueueService._instance
    legacy_initialized = BackgroundQueueService._initialized
    applications = [
        create_app(database=DatabaseLifecycle(f"sqlite:///{tmp_path / (str(index) + '.db')}"))
        for index in range(2)
    ]
    assert all(hasattr(app.state, "background_queue_service") for app in applications)
    first, second = (app.state.background_queue_service for app in applications)
    for application in applications:
        with application.state.database_lifecycle.sync_engine.begin() as connection:
            Base.metadata.create_all(connection)
    assert (
        first is not second
        and first is not legacy_instance
        and second is not legacy_instance
    )
    assert BackgroundQueueService._instance is legacy_instance
    assert BackgroundQueueService._initialized == legacy_initialized
    assert not first.is_running and not second.is_running
    seen = []
    first_done, second_done = asyncio.Event(), asyncio.Event()

    async def first_handler(payload, progress):
        seen.append(("first", payload["value"]))
        progress(100)
        first_done.set()
        return True

    async def second_handler(payload, progress):
        seen.append(("second", payload["value"]))
        progress(100)
        second_done.set()
        return True

    try:
        first.register_task_handler("scope.probe", first_handler)
        assert not second.has_handler("scope.probe")
        second.register_task_handler("scope.probe", second_handler)
        await first.start()
        await second.start()
        first_id = await first.enqueue_task(
            "scope.probe", {"streamer_name": "scope", "value": "one"}
        )
        await asyncio.wait_for(first_done.wait(), 3)
        await first.wait_for_completion()
        assert seen == [("first", "one")]
        assert second.get_task(first_id) is None
        await first.stop()
        assert second.is_running
        second_id = await second.enqueue_task(
            "scope.probe", {"streamer_name": "scope", "value": "two"}
        )
        await asyncio.wait_for(second_done.wait(), 3)
        await second.wait_for_completion()
        assert seen == [("first", "one"), ("second", "two")]
        assert first.get_task(second_id) is None
        assert (
            first.queue_manager.progress_tracker.websocket_manager
            is applications[0].state.websocket_manager
        )
        assert (
            second.queue_manager.progress_tracker.websocket_manager
            is applications[1].state.websocket_manager
        )
    finally:
        await first.stop()
        await second.stop()
        for app in applications:
            await app.state.database_lifecycle.adispose()
