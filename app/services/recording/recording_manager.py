"""Typed facade for the recording lifecycle.

The manager is the process-scoped entry point for callers that need recording
lifecycle operations. It deliberately delegates the proven lifecycle,
subprocess, rotation, recovery, and post-processing behavior to
``RecordingService`` and its orchestrator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.services.twitch_upstream_coordinator import twitch_upstream_coordinator

if TYPE_CHECKING:
    from app.services.recording.recording_service import RecordingService


@dataclass(frozen=True)
class RecordingStatus:
    """A credential-free snapshot of a locally managed recording."""

    recording_id: int
    stream_id: int | None
    streamer_id: int | None
    file_path: str | None
    status: str


@dataclass(frozen=True)
class RecordingReconciliation:
    """Result of bounded startup reconciliation."""

    reconciled_leases: int
    recovered_recording_ids: tuple[int, ...]


class RecordingManager:
    """Small, typed facade over the established recording implementation.

    Durable ownership remains the responsibility of ``TwitchUpstreamCoordinator``.
    The process dictionaries exposed by the delegated service remain local caches.
    """

    def __init__(
        self,
        service: Any | None = None,
        *,
        upstream_coordinator: Any = twitch_upstream_coordinator,
    ) -> None:
        if service is None:
            from app.services.recording.recording_service import RecordingService

            service = RecordingService()
        self._service = service
        self._upstream_coordinator = upstream_coordinator
        # Local serialization avoids duplicate start/stop races within this
        # process. Durable, cross-instance ownership remains lease-backed.
        self._lifecycle_lock = asyncio.Lock()
        self._stopped_recording_ids: set[int] = set()
        self._stopped_streamer_ids: set[int] = set()

    @property
    def recording_service(self) -> RecordingService:
        """Expose the compatibility service for legacy-only consumers."""
        return self._service

    @property
    def orchestrator(self) -> Any:
        """Preserve legacy access to focused recording collaborators."""
        return self._service.orchestrator

    @property
    def process_manager(self) -> Any:
        """Expose process inspection without making it an ownership authority."""
        return self._service.process_manager

    async def start_recording(
        self, stream_id: int, streamer_id: int, **kwargs: Any
    ) -> int | None:
        async with self._lifecycle_lock:
            for (
                recording_id,
                recording,
            ) in self._service.get_active_recordings().items():
                if recording.get("stream_id") == stream_id:
                    return recording_id

            recording_id = await self._service.start_recording(
                stream_id, streamer_id, **kwargs
            )
            if recording_id is not None:
                self._stopped_recording_ids.discard(recording_id)
                self._stopped_streamer_ids.discard(streamer_id)
            return recording_id

    async def stop_recording(self, recording_id: int, reason: str = "manual") -> bool:
        async with self._lifecycle_lock:
            if recording_id in self._stopped_recording_ids:
                return True

            stopped = await self._service.stop_recording(recording_id, reason)
            if stopped:
                self._stopped_recording_ids.add(recording_id)
            return stopped

    async def force_start_recording(self, streamer_id: int) -> int | None:
        async with self._lifecycle_lock:
            for (
                recording_id,
                recording,
            ) in self._service.get_active_recordings().items():
                if recording.get("streamer_id") == streamer_id:
                    return recording_id

            recording_id = await self._service.force_start_recording(streamer_id)
            if recording_id is not None:
                self._stopped_recording_ids.discard(recording_id)
                self._stopped_streamer_ids.discard(streamer_id)
            return recording_id

    async def stop_recording_manual(self, streamer_id: int) -> bool:
        async with self._lifecycle_lock:
            if streamer_id in self._stopped_streamer_ids:
                return True

            stopped = await self._service.stop_recording_manual(streamer_id)
            if stopped:
                self._stopped_streamer_ids.add(streamer_id)
            return stopped

    def is_stream_active(self, stream_id: int) -> bool:
        """Report whether this process already manages a stream locally."""
        return any(
            recording.get("stream_id") == stream_id
            for recording in self._service.get_active_recordings().values()
        )

    def get_status(self, recording_id: int) -> RecordingStatus | None:
        recording = self._service.get_active_recording(recording_id)
        return self._status_from_recording(recording_id, recording)

    def list_status(self) -> list[RecordingStatus]:
        statuses = []
        for recording_id, recording in self._service.get_active_recordings().items():
            status = self._status_from_recording(recording_id, recording)
            if status is not None:
                statuses.append(status)
        return sorted(statuses, key=lambda status: status.recording_id)

    def get_active_recordings(self) -> dict[int, dict[str, Any]]:
        """Compatibility view used by existing recovery and route consumers."""
        return self._service.get_active_recordings()

    async def recover_active_recordings_from_persistence(self) -> list[int]:
        """Recover persisted recordings through the established orchestrator."""
        return await self._service.recover_active_recordings_from_persistence()

    async def startup_reconcile(self) -> RecordingReconciliation:
        """Reconcile expired durable leases, then recover persisted local state."""
        reconciled_leases = await self.reconcile_leases()
        recovered_recording_ids = (
            await self.recover_active_recordings_from_persistence()
        )
        return RecordingReconciliation(
            reconciled_leases=reconciled_leases,
            recovered_recording_ids=tuple(recovered_recording_ids),
        )

    async def reconcile_leases(self) -> int:
        """Release only stale durable leases before queue-backed recovery begins."""
        return await self._upstream_coordinator.reconcile()

    async def renew_leases(self) -> int:
        """Renew leases for locally tracked process owners only.

        ProcessManager performs this during normal long-stream monitoring. This
        explicit operation exists for bounded lifecycle supervision and never
        attempts to claim a foreign or expired lease.
        """
        renewed = 0
        for segment in self.process_manager.long_stream_processes.values():
            channel_key = segment.get("upstream_channel_key")
            generation = segment.get("upstream_generation")
            if not channel_key or generation is None:
                continue
            if await self._upstream_coordinator.heartbeat(
                channel_key=channel_key, generation=generation
            ):
                renewed += 1
        return renewed

    async def shutdown(self, timeout: int | None = None) -> None:
        """Stop locally owned subprocesses before database disposal."""
        await self._service.graceful_shutdown(timeout=timeout)

    @staticmethod
    def _status_from_recording(
        recording_id: int, recording: dict[str, Any] | None
    ) -> RecordingStatus | None:
        if recording is None:
            return None
        return RecordingStatus(
            recording_id=recording_id,
            stream_id=recording.get("stream_id"),
            streamer_id=recording.get("streamer_id"),
            file_path=recording.get("file_path"),
            status=str(recording.get("status", "unknown")),
        )
