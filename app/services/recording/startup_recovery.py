"""Startup recovery: closed catalog snapshots, then provider/admission awaits."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Recording, Stream, StreamMetadata, TwitchUpstreamLease
from app.services.api.twitch_api import TwitchAPIService
from app.services.recording.media_ownership import CaptureState, capture_state
from app.services.recording.recording_manager import RecordingManager
from app.utils.async_db_utils import run_in_thread_pool

logger = logging.getLogger("streamvault")


@dataclass(frozen=True)
class StartupRecording:
    recording_id: int
    stream_id: int
    streamer_id: int
    twitch_id: str
    generation: int | None
    segments_dir: str | None


def _load_candidates(sessions: Callable[[], Session]) -> tuple[StartupRecording, ...]:
    values = []
    with sessions() as db:
        rows = db.scalars(
            select(Recording)
            .options(joinedload(Recording.stream).joinedload(Stream.streamer))
            .where(Recording.status == "recording")
        ).all()
        for row in rows:
            stream = row.stream
            if stream is None or stream.streamer is None:
                continue  # Missing ownership data cannot prove capture death.
            generation = db.scalar(
                select(TwitchUpstreamLease.generation).where(
                    TwitchUpstreamLease.channel_key == stream.streamer.twitch_id,
                    TwitchUpstreamLease.recording_id == row.id,
                )
            )
            segments = db.scalar(
                select(StreamMetadata.segments_dir_path)
                .where(StreamMetadata.stream_id == stream.id)
                .limit(1)
            )
            if segments is None or not Path(segments).exists():
                segments = None
                if row.path:
                    path = Path(row.path)
                    candidate = path.parent / (path.stem + "_segments")
                    if candidate.exists():
                        segments = str(candidate)
            values.append(
                StartupRecording(
                    row.id,
                    stream.id,
                    stream.streamer_id,
                    stream.streamer.twitch_id,
                    generation,
                    segments,
                )
            )
    return tuple(values)


def _mark_stopped(row: Recording, *, end_stream: bool) -> None:
    now = datetime.now(timezone.utc)
    row.status = "stopped"
    row.end_time = row.end_time or now
    if row.start_time is not None:
        start = row.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        end = row.end_time
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        row.duration = int((end - start).total_seconds())
    if end_stream and row.stream is not None and row.stream.ended_at is None:
        row.stream.ended_at = now


def _finish_resumed(sessions: Callable[[], Session], recording_id: int) -> None:
    with sessions() as db, db.begin():
        row = db.scalar(
            select(Recording).where(Recording.id == recording_id).with_for_update()
        )
        if row is not None and row.status == "recording":
            _mark_stopped(row, end_stream=False)


async def _finish_offline(manager: RecordingManager, value: StartupRecording) -> None:
    processes = manager.process_manager
    snapshots = await processes.capture_process_snapshot()

    def work(db: Session) -> None:
        row = db.scalar(
            select(Recording)
            .where(Recording.id == value.recording_id)
            .with_for_update()
        )
        if row is None or row.status != "recording":
            return
        if (
            capture_state(db, row, snapshots.get(f"stream_{row.stream_id}"))
            is CaptureState.DEAD
        ):
            _mark_stopped(row, end_stream=True)

    await processes.upstream_coordinator.run_capture_maintenance(work)


async def recover_startup_recordings(
    session_factory: Callable[[], Session],
    recording_manager: RecordingManager,
    twitch_api: TwitchAPIService,
) -> None:
    candidates = await run_in_thread_pool(_load_candidates, session_factory)
    for value in candidates:
        if recording_manager.is_stream_active(value.stream_id):
            continue
        try:
            is_still_live = bool(
                await twitch_api.get_streams(user_ids=[value.twitch_id])
            )
        except Exception as api_error:
            logger.warning(
                "Deferring zombie recording cleanup for %s (%s)",
                value.recording_id,
                type(api_error).__name__,
            )
            continue
        try:
            if is_still_live:
                if value.generation is None:
                    continue
                admitted = await recording_manager.start_recording(
                    stream_id=value.stream_id,
                    streamer_id=value.streamer_id,
                    force_mode=True,
                    resume_segments_dir=value.segments_dir,
                    recovery_generation=value.generation,
                )
                if admitted:
                    await run_in_thread_pool(
                        _finish_resumed, session_factory, value.recording_id
                    )
            else:
                await _finish_offline(recording_manager, value)
        except Exception as error:
            logger.error(
                "Startup recording recovery failed for %s (%s)",
                value.recording_id,
                type(error).__name__,
            )
