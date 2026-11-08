"""Startup recovery: closed snapshots and fenced mutations (adapted from #842/a34aaf69)."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import Recording, Stream, StreamMetadata, TwitchUpstreamLease
from app.services.recording.media_ownership import CaptureState, capture_state

logger = logging.getLogger("streamvault")


@dataclass(frozen=True)
class RecoveryCandidate:
    recording_id: int
    stream_id: int
    streamer_id: int
    twitch_id: str
    username: str
    generation: int | None
    segments_dir: str | None


def _load_candidates(session_factory):
    with session_factory() as db:
        rows = db.scalars(
            select(Recording)
            .options(joinedload(Recording.stream).joinedload(Stream.streamer))
            .where(Recording.status == "recording")
        ).all()
        candidates = []
        for recording in rows:
            stream = recording.stream
            if stream is None or stream.streamer is None:
                continue  # No ownership evidence: do not terminate an unknown writer.
            streamer = stream.streamer
            generation = db.scalar(
                select(TwitchUpstreamLease.generation).where(
                    TwitchUpstreamLease.channel_key == streamer.twitch_id,
                    TwitchUpstreamLease.recording_id == recording.id,
                )
            )
            metadata = db.scalar(
                select(StreamMetadata).where(StreamMetadata.stream_id == stream.id)
            )
            segments = metadata.segments_dir_path if metadata else None
            if segments and not Path(segments).exists():
                segments = None
            if not segments and recording.path:
                possible = Path(recording.path).with_suffix("").parent / (
                    Path(recording.path).stem + "_segments"
                )
                if possible.exists():
                    segments = str(possible)
            candidates.append(
                RecoveryCandidate(
                    recording.id,
                    stream.id,
                    streamer.id,
                    streamer.twitch_id,
                    streamer.username,
                    generation,
                    segments,
                )
            )
        return candidates


def _dead_recording(db, recording_id, snapshots):
    recording = db.get(Recording, recording_id, with_for_update=True)
    if recording is None or recording.status != "recording":
        return None
    if (
        capture_state(db, recording, snapshots.get(f"stream_{recording.stream_id}"))
        != CaptureState.DEAD
    ):
        return None
    return recording


def _finish_offline(db, candidate, snapshots):
    recording = _dead_recording(db, candidate.recording_id, snapshots)
    if recording is None:
        return False
    now = datetime.now(timezone.utc)
    recording.status = "stopped"
    recording.end_time = recording.end_time or now
    if recording.start_time:
        start = recording.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        recording.duration = max(
            0,
            int(
                (
                    recording.end_time.replace(tzinfo=timezone.utc) - start
                ).total_seconds()
            ),
        )
    stream = db.get(Stream, candidate.stream_id, with_for_update=True)
    if stream is not None and stream.ended_at is None:
        stream.ended_at = now
    return True


def _finish_resumed(session_factory, candidate):
    with session_factory() as db:
        prior = db.get(Recording, candidate.recording_id, with_for_update=True)
        if prior is not None and prior.status == "recording":
            now = datetime.now(timezone.utc)
            prior.status = "stopped"
            prior.end_time = now
            if prior.start_time:
                start = prior.start_time
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                prior.duration = max(0, int((now - start).total_seconds()))
            db.commit()


async def recover_startup_recordings(
    *, session_factory, recording_manager, twitch_service
):
    """Never hold a DB transaction across a provider call or capture admission."""
    candidates = await asyncio.to_thread(_load_candidates, session_factory)
    processes = recording_manager.process_manager
    resumed = stopped = 0
    for candidate in candidates:
        try:
            snapshots = await processes.capture_process_snapshot()
            # Check before provider I/O; recheck under the same guard before mutation.
            dead = await processes.upstream_coordinator.run_capture_maintenance(
                lambda db: (
                    _dead_recording(db, candidate.recording_id, snapshots) is not None
                )
            )
            if not dead or recording_manager.is_stream_active(candidate.stream_id):
                continue
            info = await twitch_service.get_streams(user_ids=[candidate.twitch_id])
            if not info:
                snapshots = await processes.capture_process_snapshot()
                stopped += bool(
                    await processes.upstream_coordinator.run_capture_maintenance(
                        lambda db: _finish_offline(db, candidate, snapshots)
                    )
                )
                continue
            if candidate.generation is None:
                continue
            new_id = await recording_manager.start_recording(
                stream_id=candidate.stream_id,
                streamer_id=candidate.streamer_id,
                force_mode=True,
                resume_segments_dir=candidate.segments_dir,
                recovery_generation=candidate.generation,
            )
            if new_id:
                await asyncio.to_thread(_finish_resumed, session_factory, candidate)
                resumed += 1
        except Exception:
            logger.exception(
                "Startup recovery deferred for recording %s", candidate.recording_id
            )
    logger.info("Startup recovery completed: resumed=%s, stopped=%s", resumed, stopped)
