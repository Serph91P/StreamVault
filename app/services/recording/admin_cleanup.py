"""Native, app-owned cleanup; age and registry absence never prove capture death."""

from collections.abc import Callable
import logging
from datetime import datetime, timedelta, timezone
from typing import NotRequired, TypedDict

from sqlalchemy.orm import Session, joinedload

from app.models import Recording, Stream
from app.services.recording.media_ownership import (
    CaptureState,
    LocalCapture,
    capture_state,
)
from app.services.recording.process_manager import ProcessManager
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


class CleanupDetail(TypedDict):
    recording_id: int
    stream_id: int | None
    streamer_id: int | None
    started_at: str | None
    duration_hours: float | None
    action: str
    streamer_name: NotRequired[str]
    process_id: NotRequired[str]
    has_active_process: NotRequired[bool]
    error: NotRequired[str]


class CleanupResult(TypedDict):
    checked: int
    cleaned: int
    errors: int
    details: list[CleanupDetail]


def _inspect_recordings(
    db: Session,
    snapshots: dict[str, LocalCapture],
    *,
    dry_run: bool,
    max_age_hours: int | None,
) -> CleanupResult:
    result: CleanupResult = {"checked": 0, "cleaned": 0, "errors": 0, "details": []}
    now = datetime.now(timezone.utc)
    query = (
        db.query(Recording)
        .options(joinedload(Recording.stream).joinedload(Stream.streamer))
        .filter(Recording.status == "recording")
    )
    if max_age_hours is not None:
        query = query.filter(
            Recording.start_time < now - timedelta(hours=max_age_hours)
        )
    if not dry_run:
        query = query.with_for_update(of=Recording)
    for recording in query.order_by(Recording.id).all():
        result["checked"] += 1
        started = recording.start_time
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        local = snapshots.get(f"stream_{recording.stream_id}")
        detail: CleanupDetail = {
            "recording_id": recording.id,
            "stream_id": recording.stream_id,
            "streamer_id": None,
            "started_at": recording.start_time.isoformat()
            if recording.start_time
            else None,
            "duration_hours": (now - started).total_seconds() / 3600
            if started
            else None,
            "action": "none",
        }
        if max_age_hours is None:
            detail["process_id"] = f"stream_{recording.stream_id}"
            detail["has_active_process"] = local is not None and not local.exited
        try:
            if recording.stream:
                detail["streamer_id"] = recording.stream.streamer_id
                if recording.stream.streamer:
                    detail["streamer_name"] = recording.stream.streamer.username
            # Reinspect persisted/local physical identity inside the admission guard.
            if capture_state(db, recording, local) is CaptureState.DEAD:
                detail["action"] = (
                    "mark_completed"
                    if max_age_hours is not None
                    else "mark_completed_no_process"
                )
                if not dry_run:
                    recording.status = "completed"
                    recording.end_time = now
                    if started:
                        recording.duration = (now - started).total_seconds()
                if not dry_run or max_age_hours is None:
                    result["cleaned"] += 1
            elif local is not None and not local.exited and max_age_hours is None:
                detail["action"] = "keep_active_process_found"
        except Exception:
            logger.exception("Error processing recording %s", recording.id)
            result["errors"] += 1
            detail["error"] = "Processing failed"
        result["details"].append(detail)
    return result


async def inspect_or_cleanup_recordings(
    manager: ProcessManager,
    session_factory: Callable[[], Session],
    *,
    dry_run: bool,
    max_age_hours: int | None = None,
) -> CleanupResult:
    snapshots = await manager.capture_process_snapshot()
    if dry_run:

        def preview() -> CleanupResult:
            with session_factory() as db:
                return _inspect_recordings(
                    db, snapshots, dry_run=True, max_age_hours=max_age_hours
                )

        result: CleanupResult = await run_in_thread_pool(preview)
    else:
        result = await manager.upstream_coordinator.run_capture_maintenance(
            lambda db: _inspect_recordings(
                db, snapshots, dry_run=False, max_age_hours=max_age_hours
            )
        )
    return result
