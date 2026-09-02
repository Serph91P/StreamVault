import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from app.models import Stream, Streamer, Recording, ActiveRecordingState

logger = logging.getLogger("streamvault")


def get_video_thumbnail_url(stream_id: int, recording_path: str) -> Optional[str]:
    """Get the correct thumbnail URL for a video (null fallback).

    Kept in the catalog service so both the video-catalog read model and the
    router can resolve thumbnails without running ad-hoc filesystem logic in
    the router layer.
    """
    try:
        recording_path_obj = Path(recording_path)
        base_filename = recording_path_obj.stem
        video_dir = recording_path_obj.parent

        thumbnail_candidates = [
            video_dir / f"{base_filename}-thumb.jpg",
            video_dir / f"{base_filename}_thumbnail.jpg",
        ]

        for thumbnail_path in thumbnail_candidates:
            if thumbnail_path.exists() and thumbnail_path.is_file():
                return f"/api/videos/{stream_id}/thumbnail"

        return None
    except Exception as e:
        logger.error(f"Error getting thumbnail for stream {stream_id}: {e}")
        return None


class VideoCatalogService:
    """Read-model seam for the `/api/videos` catalog (Phase 4A, issue #826).

    Extracts the DB-backed catalog queries (including the legacy three-strategy
    merge) from the videos router so the router no longer runs ad-hoc sync SQL
    for the primary video-listing domain.
    """

    def __init__(self, db: Session):
        self.db = db

    def list_all_videos(self) -> list:
        """Build the full catalog using the legacy three-strategy merge."""
        videos = []

        # Strategy 1: streams that have recording_path set
        streams_with_paths = (
            self.db.query(Stream, Streamer)
            .join(Streamer, Stream.streamer_id == Streamer.id)
            .filter(Stream.recording_path.isnot(None), Stream.recording_path != "")
            .order_by(Stream.started_at.desc())
            .all()
        )

        logger.debug(f"Found {len(streams_with_paths)} streams with recording paths")

        for stream, streamer in streams_with_paths:
            try:
                recording_path = Path(stream.recording_path)

                if recording_path.exists() and recording_path.is_file():
                    file_stats = recording_path.stat()

                    duration = None
                    if stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()

                    thumbnail_url = get_video_thumbnail_url(
                        stream.id, str(recording_path)
                    )

                    videos.append(
                        {
                            "id": stream.id,
                            "title": stream.title or f"Stream {stream.id}",
                            "streamer_name": streamer.username,
                            "streamer_id": streamer.id,
                            "file_path": str(recording_path),
                            "file_size": file_stats.st_size,
                            "created_at": stream.started_at.isoformat()
                            if stream.started_at
                            else None,
                            "started_at": stream.started_at.isoformat()
                            if stream.started_at
                            else None,
                            "ended_at": stream.ended_at.isoformat()
                            if stream.ended_at
                            else None,
                            "duration": duration,
                            "category_name": stream.category_name,
                            "language": stream.language,
                            "thumbnail_url": thumbnail_url,
                            "has_thumbnail": thumbnail_url is not None,
                        }
                    )
            except Exception as e:
                logger.error(f"Error processing stream {stream.id}: {e}")
                continue

        # Strategy 2: recordings with valid files but no recording_path in stream
        recordings_with_files = (
            self.db.query(Recording, Stream, Streamer)
            .join(Stream, Recording.stream_id == Stream.id)
            .join(Streamer, Stream.streamer_id == Streamer.id)
            .filter(
                Recording.path.isnot(None),
                Recording.path != "",
                Recording.status.in_(["completed", "post_processing"]),
            )
            .order_by(Recording.start_time.desc())
            .all()
        )

        added_stream_ids = {video["id"] for video in videos}

        for recording, stream, streamer in recordings_with_files:
            if stream.id in added_stream_ids:
                continue
            try:
                recording_path = Path(recording.path)
                mp4_path = recording_path.with_suffix(".mp4")

                final_path = None
                recording_file_stats: os.stat_result | None = None

                if mp4_path.exists():
                    final_path = mp4_path
                    recording_file_stats = mp4_path.stat()
                elif recording_path.exists():
                    final_path = recording_path
                    recording_file_stats = recording_path.stat()

                if final_path and recording_file_stats:
                    if not stream.recording_path:
                        stream.recording_path = str(final_path)
                        logger.debug(
                            f"Auto-updated recording_path for stream {stream.id}: {final_path}"
                        )

                    duration = None
                    if recording.start_time and recording.end_time:
                        duration = (
                            recording.end_time - recording.start_time
                        ).total_seconds()
                    elif stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()

                    thumbnail_url = get_video_thumbnail_url(stream.id, str(final_path))

                    videos.append(
                        {
                            "id": stream.id,
                            "title": stream.title or f"Stream {stream.id}",
                            "streamer_name": streamer.username,
                            "streamer_id": streamer.id,
                            "file_path": str(final_path),
                            "file_size": recording_file_stats.st_size,
                            "created_at": (
                                (recording.start_time or stream.started_at).isoformat()
                                if (recording.start_time or stream.started_at)
                                else None
                            ),
                            "started_at": (
                                (recording.start_time or stream.started_at).isoformat()
                                if (recording.start_time or stream.started_at)
                                else None
                            ),
                            "ended_at": (
                                (recording.end_time or stream.ended_at).isoformat()
                                if (recording.end_time or stream.ended_at)
                                else None
                            ),
                            "duration": duration,
                            "category_name": stream.category_name,
                            "language": stream.language,
                            "thumbnail_url": thumbnail_url,
                            "has_thumbnail": thumbnail_url is not None,
                        }
                    )
                    added_stream_ids.add(stream.id)
            except Exception as e:
                logger.error(f"Error processing recording {recording.id}: {e}")
                continue

        # Strategy 3: currently-recording streams surfaced before the recording
        # finishes, pulled from ActiveRecordingState (same source the recovery
        # loop trusts). The .ts file may still be growing, so report best-effort
        # size and mark is_recording=True for a "Live recording" badge.
        try:
            active_states = (
                self.db.query(ActiveRecordingState, Stream, Streamer)
                .join(Stream, ActiveRecordingState.stream_id == Stream.id)
                .join(Streamer, Stream.streamer_id == Streamer.id)
                .filter(ActiveRecordingState.status == "active")
                .all()
            )

            for state, stream, streamer in active_states:
                if stream.id in added_stream_ids:
                    continue
                try:
                    ts_path = (
                        Path(state.ts_output_path) if state.ts_output_path else None
                    )
                    file_size = 0
                    file_path_str = str(ts_path) if ts_path else None
                    if ts_path and ts_path.exists() and ts_path.is_file():
                        file_size = ts_path.stat().st_size

                    started = state.started_at or stream.started_at
                    duration = None
                    if started:
                        duration = (
                            datetime.now(timezone.utc) - started
                        ).total_seconds()

                    thumbnail_url = (
                        get_video_thumbnail_url(stream.id, file_path_str)
                        if file_path_str
                        else None
                    )

                    videos.append(
                        {
                            "id": stream.id,
                            "title": stream.title or f"Stream {stream.id}",
                            "streamer_name": streamer.username,
                            "streamer_id": streamer.id,
                            "file_path": file_path_str,
                            "file_size": file_size,
                            "created_at": started.isoformat() if started else None,
                            "started_at": started.isoformat() if started else None,
                            "ended_at": None,
                            "duration": duration,
                            "category_name": stream.category_name,
                            "language": stream.language,
                            "thumbnail_url": thumbnail_url,
                            "has_thumbnail": thumbnail_url is not None,
                            "is_recording": True,
                            "recording_id": state.recording_id,
                        }
                    )
                    added_stream_ids.add(stream.id)
                except Exception as e:
                    logger.error(
                        f"Error surfacing active recording {state.recording_id}: {e}"
                    )
                    continue
        except Exception as e:
            logger.error(f"Error querying active recording states: {e}")

        # Commit any auto-updates to recording_path (idempotent self-healing)
        if len(videos) > len(streams_with_paths):
            self.db.commit()
            logger.debug(
                f"Auto-updated {len(videos) - len(streams_with_paths)} recording paths"
            )

        logger.info(f"Returning {len(videos)} videos")
        return videos

    def list_for_streamer(self, streamer_id: int) -> list:
        """Get all videos for a specific streamer."""
        videos = []
        streams = (
            self.db.query(Stream, Streamer)
            .join(Streamer, Stream.streamer_id == Streamer.id)
            .filter(
                Stream.streamer_id == streamer_id,
                Stream.recording_path.isnot(None),
                Stream.recording_path != "",
            )
            .order_by(Stream.started_at.desc())
            .all()
        )

        for stream, streamer in streams:
            try:
                recording_path = Path(stream.recording_path)
                is_finished_file = recording_path.exists() and recording_path.is_file()
                is_segmented_dir = (
                    recording_path.exists()
                    and recording_path.is_dir()
                    and recording_path.name.endswith("_segments")
                )

                if is_finished_file or is_segmented_dir:
                    if is_finished_file:
                        file_stats = recording_path.stat()
                        file_size = file_stats.st_size
                    else:
                        file_size = sum(
                            f.stat().st_size
                            for f in recording_path.glob("*.ts")
                            if f.is_file()
                        )

                    duration = None
                    if stream.started_at and stream.ended_at:
                        duration = (stream.ended_at - stream.started_at).total_seconds()

                    thumbnail_url = get_video_thumbnail_url(
                        stream.id, str(recording_path)
                    )

                    videos.append(
                        {
                            "id": stream.id,
                            "title": stream.title or f"Stream {stream.id}",
                            "streamer_name": streamer.username,
                            "streamer_id": streamer.id,
                            "file_path": str(recording_path),
                            "file_size": file_size,
                            "created_at": stream.started_at.isoformat()
                            if stream.started_at
                            else None,
                            "started_at": stream.started_at.isoformat()
                            if stream.started_at
                            else None,
                            "ended_at": stream.ended_at.isoformat()
                            if stream.ended_at
                            else None,
                            "duration": duration,
                            "category_name": stream.category_name,
                            "language": stream.language,
                            "thumbnail_url": thumbnail_url,
                            "has_thumbnail": thumbnail_url is not None,
                            "is_segmented": is_segmented_dir,
                        }
                    )
                else:
                    logger.warning(f"Recording file not found: {stream.recording_path}")
            except Exception as e:
                logger.error(f"Error processing stream {stream.id}: {e}")
                continue

        logger.info(f"Returning {len(videos)} videos for streamer {streamer_id}")
        return videos
