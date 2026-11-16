"""Mounted admin cleanup reports dependency faults, not successful mutations.

Only the owned component's exception is injected; routing/auth/dependency binding
and native queue registries remain real. No provider or media completion claim.
"""

import pytest

from app.services.background_queue_cleanup_service import BackgroundQueueCleanupService
from tests.test_image_http_ownership import image_applications as image_applications


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,method,detail",
    [
        ("all", "comprehensive_cleanup", "Cleanup failed"),
        (
            "stuck-recordings",
            "cleanup_stuck_recording_tasks",
            "Stuck recordings cleanup failed",
        ),
        (
            "orphaned-recovery",
            "stop_continuous_orphaned_recovery",
            "Orphaned recovery stop failed",
        ),
        ("task-names", "fix_unknown_task_names", "Task names fix failed"),
    ],
)
async def test_admin_cleanup_dependency_error_is_sanitized_and_preserves_both_owners(
    image_applications, monkeypatch, endpoint, method, detail
):
    apps, _databases, clients, _ = image_applications
    own, peer = (app.state.background_queue_service for app in apps)
    own.add_external_task("own-fixture", "unknown", {})
    peer.add_external_task("peer-fixture", "unknown", {})

    def snapshot(queue):
        return {
            identity: (task.task_type, task.status, task.progress)
            for identity, task in queue.external_tasks.items()
        }

    before = [snapshot(own), snapshot(peer)]
    owners = []

    async def failed(self, *args, **kwargs):
        owners.append(self.background_queue_service is own)
        raise RuntimeError("synthetic-private-cleanup-component-detail")

    monkeypatch.setattr(BackgroundQueueCleanupService, method, failed)
    try:
        response = await clients[0].post(
            "/api/admin/background-queue/cleanup/" + endpoint
        )
        assert response.status_code == 500
        assert response.json()["detail"] == detail
        assert "synthetic-private" not in response.text
        assert owners == [True]
        assert [snapshot(own), snapshot(peer)] == before
    finally:
        await own.stop()
        await peer.stop()


@pytest.mark.asyncio
async def test_admin_orphan_stop_empty_own_registry_leaves_peer_untouched(
    image_applications,
):
    apps, _databases, clients, _ = image_applications
    own, peer = (app.state.background_queue_service for app in apps)
    peer.add_external_task("peer-fixture", "orphaned_recovery_check", {})
    try:
        response = await clients[0].post(
            "/api/admin/background-queue/cleanup/orphaned-recovery"
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["orphaned_recovery_stopped"] == data["total_issues_fixed"] == 0
        assert data["errors"] == []
        assert len(peer.external_tasks) == 1
    finally:
        await own.stop()
        await peer.stop()


@pytest.mark.asyncio
async def test_admin_queue_status_reports_native_active_and_external_conditions_without_peer_tasks(
    image_applications,
):
    import asyncio

    apps, _databases, clients, _ = image_applications
    own, peer = (app.state.background_queue_service for app in apps)
    own.add_external_task("recording_7", "recording", {})
    own.update_external_task_progress("recording_7", 100)
    own.add_external_task("recording_8", "recording", {})
    own.update_external_task_progress("recording_8", 99)
    own.add_external_task("own-unknown", "unknown", {})
    peer.add_external_task("recording_99", "recording", {})
    peer.update_external_task_progress("recording_99", 100)
    release = asyncio.Event()

    async def held(_payload, _progress=None):
        await release.wait()

    own.register_task_handler("orphaned_recovery_check", held)
    try:
        await own.start()
        identity = await own.enqueue_task("orphaned_recovery_check", {}, max_retries=0)

        async def active():
            while identity not in own.active_tasks:
                await asyncio.sleep(0.001)

        await asyncio.wait_for(active(), 3)
        response = await clients[0].get("/api/admin/background-queue/status")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_external_tasks"] == 3 and data["total_active_tasks"] == 1
        assert data["stuck_recording_tasks"] == ["recording_7"]
        assert data["orphaned_recovery_tasks"] == [identity]
        assert data["unknown_task_names"] == ["own-unknown"]
        assert data["total_issues"] == 3
        assert "recording_99" not in response.text
        assert peer.external_tasks["recording_99"].progress == 100
    finally:
        release.set()
        await own.stop()
        await peer.stop()
