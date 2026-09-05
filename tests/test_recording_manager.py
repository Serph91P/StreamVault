import asyncio
import importlib
import inspect
from types import SimpleNamespace

import pytest


class FakeRecordingService:
    def __init__(self) -> None:
        self.active = {
            7: {
                "stream_id": 70,
                "streamer_id": 17,
                "file_path": "/recordings/example.ts",
                "status": "recording",
            }
        }
        self.process_manager = SimpleNamespace(
            long_stream_processes={
                "stream_70": {
                    "upstream_channel_key": "channel-70",
                    "upstream_generation": 3,
                }
            }
        )
        self.orchestrator = SimpleNamespace(process_manager=self.process_manager)
        self.calls = []

    async def start_recording(self, stream_id: int, streamer_id: int, **kwargs):
        self.calls.append(("start", stream_id, streamer_id, kwargs))
        return 8

    async def stop_recording(self, recording_id: int, reason: str = "manual") -> bool:
        self.calls.append(("stop", recording_id, reason))
        return True

    async def force_start_recording(self, streamer_id: int):
        self.calls.append(("force", streamer_id))
        return 9

    async def stop_recording_manual(self, streamer_id: int) -> bool:
        self.calls.append(("manual-stop", streamer_id))
        return True

    def get_active_recordings(self):
        return self.active.copy()

    def get_active_recording(self, recording_id: int):
        return self.active.get(recording_id)

    async def recover_active_recordings_from_persistence(self):
        self.calls.append(("recover",))
        return [7]

    async def graceful_shutdown(self, timeout: int | None = None) -> None:
        self.calls.append(("shutdown", timeout))


class FakeCoordinator:
    def __init__(self) -> None:
        self.heartbeats = []

    async def reconcile(self) -> int:
        return 2

    async def heartbeat(self, *, channel_key: str, generation: int) -> bool:
        self.heartbeats.append((channel_key, generation))
        return True


@pytest.mark.asyncio
async def test_manager_delegates_lifecycle_and_exposes_typed_statuses() -> None:
    from app.services.recording.recording_manager import RecordingManager

    service = FakeRecordingService()
    manager = RecordingManager(service=service, upstream_coordinator=FakeCoordinator())

    assert await manager.start_recording(71, 17, quality="best") == 8
    assert await manager.stop_recording(7, reason="automatic") is True
    assert await manager.force_start_recording(18) == 9
    assert await manager.stop_recording_manual(18) is True

    status = manager.get_status(7)
    assert status is not None
    assert (
        status.recording_id,
        status.stream_id,
        status.streamer_id,
        status.status,
    ) == (
        7,
        70,
        17,
        "recording",
    )
    assert manager.list_status() == [status]
    assert manager.orchestrator is service.orchestrator
    assert manager.process_manager is service.process_manager
    assert manager.is_stream_active(70)


@pytest.mark.asyncio
async def test_manager_serializes_duplicate_starts_and_repeated_stops() -> None:
    from app.services.recording.recording_manager import RecordingManager

    class ConcurrentRecordingService(FakeRecordingService):
        def __init__(self) -> None:
            super().__init__()
            self.active = {}

        async def start_recording(self, stream_id: int, streamer_id: int, **kwargs):
            self.calls.append(("start", stream_id, streamer_id, kwargs))
            await asyncio.sleep(0)
            self.active[8] = {
                "stream_id": stream_id,
                "streamer_id": streamer_id,
                "status": "recording",
            }
            return 8

    service = ConcurrentRecordingService()
    manager = RecordingManager(service=service, upstream_coordinator=FakeCoordinator())

    started = await asyncio.gather(
        manager.start_recording(70, 17), manager.start_recording(70, 17)
    )
    assert started == [8, 8]
    assert [call[0] for call in service.calls] == ["start"]

    assert await manager.stop_recording(8, reason="automatic") is True
    assert await manager.stop_recording(8, reason="automatic") is True
    assert [call[0] for call in service.calls] == ["start", "stop"]


@pytest.mark.asyncio
async def test_manager_serializes_manual_recording_commands() -> None:
    from app.services.recording.recording_manager import RecordingManager

    service = FakeRecordingService()
    service.active = {}
    manager = RecordingManager(service=service, upstream_coordinator=FakeCoordinator())

    assert await manager.force_start_recording(17) == 9
    assert await manager.stop_recording_manual(17) is True
    assert await manager.stop_recording_manual(17) is True
    assert [call[0] for call in service.calls] == ["force", "manual-stop"]


@pytest.mark.asyncio
async def test_persisted_state_is_keyed_by_recording_id(monkeypatch) -> None:
    state_module = importlib.import_module(
        "app.services.recording.recording_state_manager"
    )

    expected = SimpleNamespace(recording_id=7, stream_id=70)

    class Persistence:
        async def load_state(self):
            return [expected]

    monkeypatch.setattr(state_module, "state_persistence_service", Persistence())
    state_manager = state_module.RecordingStateManager()

    assert await state_manager.load_state_from_persistence() == {7: expected}


@pytest.mark.asyncio
async def test_manager_reconciles_persisted_lease_and_renews_only_local_owners() -> (
    None
):
    from app.services.recording.recording_manager import RecordingManager

    service = FakeRecordingService()
    coordinator = FakeCoordinator()
    manager = RecordingManager(service=service, upstream_coordinator=coordinator)

    report = await manager.startup_reconcile()
    assert (report.reconciled_leases, report.recovered_recording_ids) == (2, (7,))
    assert await manager.renew_leases() == 1
    assert coordinator.heartbeats == [("channel-70", 3)]

    await manager.shutdown(timeout=12)
    assert service.calls == [("recover",), ("shutdown", 12)]


def test_recording_routes_share_the_dependency_manager(monkeypatch) -> None:
    from app import dependencies
    from app.routes import recording, recordings

    sentinel = object()
    monkeypatch.setattr(dependencies, "recording_manager", sentinel)

    assert recording.get_recording_service() is sentinel
    assert recordings.get_recording_service() is sentinel


def test_lifespan_owns_the_recording_manager_before_background_services() -> None:
    from app.lifespan import lifespan

    source = inspect.getsource(lifespan)
    assert source.index("get_recording_manager") < source.index(
        "initialize_background_services"
    )
    assert "app.state.recording_manager" in source
    assert source.index("recording_manager.shutdown") < source.index(
        "database_lifecycle.adispose"
    )
