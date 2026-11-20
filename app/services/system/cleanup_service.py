import os
import json
import logging
import shutil
from datetime import datetime, timedelta, time, timezone
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import Session
from pydantic import TypeAdapter, ValidationError

from app.models import (
    Category,
    Stream,
    Streamer,
    RecordingSettings,
    StreamerRecordingSettings,
    FavoriteCategory,
    StreamMetadata,
)
from app.database import SessionLocal
from app.schemas.recording import (
    CleanupPolicySchema,
    CleanupPolicyType,
    MAX_RECORDING_COUNT,
    MaxStreams,
    utc_datetime,
)
from app.utils.security import validate_path_security, is_path_within_base
from app.config.settings import get_settings
from app.config.settings import Settings
from app.utils.async_db_utils import run_in_thread_pool
from collections.abc import Callable
from app.services.system.logging_service import LoggingService

logger = logging.getLogger("streamvault")
_max_streams_adapter: TypeAdapter[int] = TypeAdapter(MaxStreams)


class InvalidRetentionPolicy(ValueError):
    """An invalid cleanup instruction must not fall through to another policy."""


def _validated_policy(value: object, source: str) -> CleanupPolicySchema:
    try:
        return CleanupPolicySchema.model_validate(value)
    except ValidationError as error:
        issue = error.errors(include_url=False, include_input=False)[0]
        field = ".".join(map(str, issue["loc"])) or "cleanup_policy"
        raise InvalidRetentionPolicy(
            f"Invalid {source} retention policy: {field}: {issue['msg']}. Correct the cleanup settings before retrying."
        ) from None


class CleanupService:
    """Service for cleaning up old recordings with advanced policies"""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = None,
        settings: Settings | None = None,
        activity_logger: LoggingService | None = None,
    ) -> None:
        self._session_factory = session_factory or SessionLocal
        self._settings = settings
        self._activity_logger = activity_logger

    @property
    def _logger(self) -> logging.Logger:
        return (
            self._activity_logger.recording_logger
            if self._activity_logger is not None
            else logger
        )

    def _validate_path(self, path: str, operation: str = "access") -> str:
        return validate_path_security(
            path,
            operation,
            recording_directory=self._settings.RECORDING_DIRECTORY
            if self._settings is not None
            else None,
        )

    async def cleanup_old_recordings(
        self, streamer_id: int, custom_policy: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, List[str]]:
        return await run_in_thread_pool(
            self._cleanup_old_recordings, streamer_id, custom_policy=custom_policy
        )

    async def get_storage_usage(self, streamer_id: int) -> Dict[str, Any]:
        return await run_in_thread_pool(self._get_storage_usage, streamer_id)

    async def run_scheduled_cleanup(self) -> None:
        await run_in_thread_pool(self._run_scheduled_cleanup)

    async def simulate_cleanup(
        self, streamer_id: int, custom_policy: Optional[Dict[str, Any]] = None
    ) -> tuple[int, dict[str, object] | list[dict[str, object]]]:
        return await run_in_thread_pool(
            self._simulate_cleanup, streamer_id, custom_policy=custom_policy
        )

    async def cleanup_orphaned_files(
        self, recordings_root: Optional[str] = None
    ) -> Tuple[int, List[str]]:
        return await run_in_thread_pool(self._cleanup_orphaned_files, recordings_root)

    def _parse_cleanup_policy(
        self, policy_str: str, source: str
    ) -> CleanupPolicySchema:
        try:
            raw = json.loads(policy_str)
        except ValueError, TypeError, RecursionError:
            raise InvalidRetentionPolicy(
                f"Invalid {source} retention policy: cleanup_policy is not valid JSON. Correct the cleanup settings before retrying."
            ) from None
        return _validated_policy(raw, source)

    def _get_effective_cleanup_policy(
        self, streamer_id: int, db: Session
    ) -> CleanupPolicySchema | None:
        channel = (
            db.query(StreamerRecordingSettings)
            .filter_by(streamer_id=streamer_id)
            .first()
        )
        if (
            channel
            and not channel.use_global_cleanup_policy
            and channel.cleanup_policy is not None
        ):
            return self._parse_cleanup_policy(channel.cleanup_policy, "channel")

        global_settings = db.query(RecordingSettings).first()
        if global_settings and global_settings.cleanup_policy is not None:
            return self._parse_cleanup_policy(global_settings.cleanup_policy, "global")

        # Validate the legacy limit before comparing or falling back. A channel
        # override wins when positive; the effective limit 0 means unlimited.
        for source, field, raw_limit in (
            ("channel", "max_streams", channel.max_streams if channel else None),
            (
                "global",
                "max_streams_per_streamer",
                global_settings.max_streams_per_streamer if global_settings else None,
            ),
        ):
            if raw_limit is None:
                continue
            try:
                limit = _max_streams_adapter.validate_python(raw_limit)
            except ValidationError:
                raise InvalidRetentionPolicy(
                    f"Invalid {source} retention policy: {field} must be an integer from 0 to {MAX_RECORDING_COUNT}. Correct the cleanup settings before retrying."
                ) from None
            if limit > 0:
                return CleanupPolicySchema(
                    type=CleanupPolicyType.COUNT,
                    threshold=limit,
                    preserve_categories=[],
                )
        return None

    def _resolve_policy(
        self, streamer_id: int, db: Session, custom_policy: dict[str, Any] | None
    ) -> CleanupPolicySchema | None:
        if custom_policy is not None:
            return _validated_policy(custom_policy, "custom")
        return self._get_effective_cleanup_policy(streamer_id, db)

    def _cleanup_old_recordings(
        self,
        streamer_id: int,
        db: Optional[Session] = None,
        custom_policy: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, List[str]]:
        close_db = db is None
        if db is None:
            db = self._session_factory()
        try:
            policy = self._resolve_policy(streamer_id, db, custom_policy)
            if policy is None:
                return 0, []
            return self._delete_streams(
                self._select_streams(streamer_id, db, policy), db
            )
        except InvalidRetentionPolicy:
            raise
        except Exception as e:
            self._logger.error(f"Error cleaning up recordings: {e}", exc_info=True)
            return 0, []
        finally:
            if close_db:
                db.close()

    def _select_streams(
        self, streamer_id: int, db: Session, policy: CleanupPolicySchema
    ) -> list[Stream]:
        now = datetime.now(timezone.utc)
        # Include completed history with missing media, but never active or
        # recently completed streams (still eligible for post-processing).
        query = db.query(Stream).filter(
            Stream.streamer_id == streamer_id,
            Stream.ended_at < now - timedelta(minutes=5),
        )
        if policy.type == CleanupPolicyType.AGE:
            query = query.filter(
                Stream.started_at < now - timedelta(days=policy.threshold)
            )
        order = (
            Stream.started_at.asc()
            if policy.type == CleanupPolicyType.SIZE
            else Stream.started_at.desc()
        )
        streams = query.order_by(order, Stream.id).all()
        favorite_names = (
            {
                name
                for (name,) in db.query(Category.name)
                .join(FavoriteCategory)
                .distinct()
                .all()
            }
            if policy.preserve_favorites
            else set()
        )
        protected_categories = favorite_names.union(policy.preserve_categories or [])
        preserved = {
            stream.id
            for stream in streams
            if stream.category_name in protected_categories
        }
        if policy.preserve_timeframe is not None:
            preserved.update(
                self._get_streams_in_timeframe(
                    streams, policy.preserve_timeframe.model_dump()
                )
            )
        unprotected = [stream for stream in streams if stream.id not in preserved]
        if policy.type == CleanupPolicyType.COUNT:
            return unprotected[policy.threshold :]
        if policy.type == CleanupPolicyType.AGE:
            return unprotected

        sizes: dict[int, int] = {}
        for stream in streams:
            if stream.recording_path and os.path.exists(stream.recording_path):
                try:
                    sizes[stream.id] = os.path.getsize(stream.recording_path)
                except OSError as error:
                    self._logger.error(
                        f"Error getting file size for {stream.recording_path}: {error}"
                    )
        remaining_size = sum(sizes.values())
        threshold_bytes = policy.threshold * 1024**3
        selected = []
        for stream in unprotected:
            if remaining_size <= threshold_bytes:
                break
            if stream.id in sizes:
                selected.append(stream)
                remaining_size -= sizes[stream.id]
        return selected

    def _get_streams_in_timeframe(
        self, streams: list[Stream], timeframe: dict[str, Any]
    ) -> set[int]:
        start_date = timeframe.get("start_date")
        end_date = timeframe.get("end_date")
        start = utc_datetime(datetime.fromisoformat(start_date)) if start_date else None
        end = utc_datetime(datetime.fromisoformat(end_date)) if end_date else None
        weekdays = timeframe.get("weekdays")
        clock = timeframe.get("timeOfDay")
        if clock:
            start_hour, start_minute = map(int, clock["start"].split(":"))
            end_hour, end_minute = map(int, clock["end"].split(":"))
            start_time = time(start_hour, start_minute)
            end_time = time(end_hour, end_minute)
        preserved = set()
        for stream in streams:
            if stream.started_at is None:
                continue
            started = utc_datetime(stream.started_at)
            if (start and started < start) or (end and started > end):
                continue
            if weekdays and started.weekday() not in weekdays:
                continue
            if clock:
                current = started.time()
                if end_time > start_time:
                    if not start_time <= current <= end_time:
                        continue
                elif not (current >= start_time or current <= end_time):
                    continue
            preserved.add(stream.id)
        return preserved

    def _delete_streams(
        self, streams_to_delete: List[Stream], db: Session
    ) -> Tuple[int, List[str]]:
        """Delete the specified streams and return count and paths"""
        deleted_count = 0
        deleted_paths = []

        for stream in streams_to_delete:
            try:
                # BREAKING CHANGE: Complete stream record deletion
                # Previous behavior: Only cleared recording_path field
                # New behavior: Deletes entire stream record and all associated files
                # Reason: Provides complete cleanup and prevents database bloat
                # Trade-off: Stream history is lost (view count, timestamps, etc.)
                # Alternative: Use preserve_favorites or preserve_timeframe to keep important streams

                # Get all metadata files from database first
                metadata = (
                    db.query(StreamMetadata)
                    .filter(StreamMetadata.stream_id == stream.id)
                    .first()
                )
                files_to_delete: list[str] = []
                directories_to_check = set()
                required_directories = set()
                deletion_failed = False
                removed_candidates = set()
                from app.models import Recording

                associated_recordings = (
                    db.query(Recording).filter(Recording.stream_id == stream.id).all()
                )
                files_to_delete.extend(
                    recording.path
                    for recording in associated_recordings
                    if recording.path
                )

                # Get the base directory for this recording
                recording_dir = None
                if stream.recording_path:
                    recording_dir = os.path.dirname(stream.recording_path)
                    if recording_dir and os.path.exists(recording_dir):
                        directories_to_check.add(recording_dir)
                elif metadata and metadata.nfo_path:
                    # If no recording_path but metadata exists, use metadata path to find directory
                    recording_dir = os.path.dirname(metadata.nfo_path)
                    if recording_dir and os.path.exists(recording_dir):
                        directories_to_check.add(recording_dir)

                # Add main recording file
                if stream.recording_path:
                    files_to_delete.append(stream.recording_path)

                # Add all metadata files from database (only actually generated files)
                # NOTE: We use ONLY database paths - NO pattern matching!
                # This prevents accidental deletion of files belonging to other streams
                if metadata:
                    # Per-stream files (unique to this stream, safe to delete)
                    per_stream_files = [
                        metadata.thumbnail_path,
                        metadata.json_path,
                        metadata.nfo_path,  # Episode-specific NFO
                        metadata.chapters_vtt_path,
                        metadata.chapters_srt_path,
                        metadata.chapters_ffmpeg_path,
                        metadata.chapters_xml_path,
                    ]

                    # Add existing per-stream files to deletion list
                    for file_path in per_stream_files:
                        if file_path:
                            files_to_delete.append(file_path)

                    # SHARED FILES HANDLING:
                    # - tvshow.nfo: Belongs to STREAMER, not streams. NEVER delete during stream cleanup.
                    #               Only delete when the STREAMER is deleted (handled in streamer deletion route)
                    # - season.nfo: Belongs to SEASON. Only delete if this is the LAST stream in that season.
                    if metadata.tvshow_nfo_path:
                        # NEVER delete tvshow.nfo during stream cleanup - it belongs to the streamer
                        self._logger.debug(
                            f"Preserving tvshow.nfo (belongs to streamer, not stream): {metadata.tvshow_nfo_path}"
                        )

                    if metadata.season_nfo_path:
                        # Check if other streams exist in the same season directory
                        season_dir = os.path.dirname(metadata.season_nfo_path)
                        other_streams_in_season = (
                            db.query(Stream)
                            .join(StreamMetadata)
                            .filter(
                                Stream.streamer_id == stream.streamer_id,
                                Stream.id != stream.id,
                                StreamMetadata.season_nfo_path.like(f"{season_dir}%"),
                            )
                            .count()
                        )
                        if other_streams_in_season == 0:
                            files_to_delete.append(metadata.season_nfo_path)
                            self._logger.debug(
                                f"Last stream in season, will delete season.nfo: {metadata.season_nfo_path}"
                            )
                        else:
                            self._logger.debug(
                                f"Keeping shared season.nfo (other streams in season): {metadata.season_nfo_path}"
                            )

                    # Add segments directory from database if tracked
                    if (
                        hasattr(metadata, "segments_dir_path")
                        and metadata.segments_dir_path
                    ):
                        directories_to_check.add(metadata.segments_dir_path)
                        required_directories.add(metadata.segments_dir_path)

                # Fallback: Derive segments directory from recording_path if not in DB
                if stream.recording_path:
                    segments_dir_derived = stream.recording_path.replace(
                        ".mp4", "_segments"
                    ).replace(".ts", "_segments")
                    directories_to_check.add(segments_dir_derived)
                    required_directories.add(segments_dir_derived)

                # Delete all collected files (using exact DB paths only)
                files_to_delete = list(dict.fromkeys(files_to_delete))
                for file_path in files_to_delete:
                    try:
                        self._validate_path(file_path, "access")
                        os.remove(file_path)
                        removed_candidates.add(file_path)
                    except FileNotFoundError:
                        pass
                    except Exception as e:
                        deletion_failed = True
                        self._logger.error(f"Failed to delete file {file_path}: {e}")

                # Delete segment directories if they exist and are not actively being used
                for dir_path in directories_to_check:
                    # Skip if not a segments directory (recording_dir may be added for other checks)
                    if not dir_path.endswith("_segments"):
                        continue

                    if os.path.exists(dir_path) and os.path.isdir(dir_path):
                        # Safety check: Don't delete if this stream is still active
                        if stream.ended_at is None:
                            self._logger.warning(
                                f"Skipping deletion of segment directory for active recording: {dir_path}"
                            )
                            continue

                        try:
                            self._validate_path(dir_path, "delete")
                            shutil.rmtree(dir_path)
                            self._logger.info(f"Deleted segment directory: {dir_path}")
                        except Exception as e:
                            deletion_failed = True
                            self._logger.error(
                                f"Failed to delete directory {dir_path}: {e}"
                            )

                for required_path in dict.fromkeys(
                    [*files_to_delete, *required_directories]
                ):
                    try:
                        os.lstat(required_path)
                    except FileNotFoundError:
                        if required_path in removed_candidates:
                            deleted_paths.append(required_path)
                        continue
                    except OSError as e:
                        self._logger.error(
                            "Cannot verify deletion of %s: %s", required_path, e
                        )
                    deletion_failed = True

                if deletion_failed:
                    self._logger.error(
                        "Retaining catalog for stream %s: required deletion failed or absence is unverified",
                        stream.id,
                    )
                    continue

                # Delete associated recordings BEFORE deleting the stream
                # This prevents IntegrityError: null value in column "stream_id" violates not-null constraint
                # Even though we have ondelete="CASCADE", SQLAlchemy's cascade behavior requires explicit deletion
                for recording in associated_recordings:
                    db.delete(recording)
                    self._logger.debug(
                        f"Deleted recording {recording.id} for stream {stream.id}"
                    )

                # Delete metadata record from database
                if metadata:
                    db.delete(metadata)
                    self._logger.debug(
                        f"Deleted metadata record for stream {stream.id}"
                    )

                # Delete the stream record completely from database
                # (Cleanup should remove the entire stream record, not just clear recording_path)
                db.delete(stream)

                deleted_count += 1
                file_count = len(files_to_delete)
                dir_count = len(directories_to_check)
                self._logger.info(
                    f"Deleted stream {stream.id} with {file_count} files and {dir_count} directories"
                )

                # ARCHITECTURE NOTE: StreamVault stores recordings directly in Season folders
                # Structure: /recordings/{Streamer}/Season YYYY-MM/{Episode files}
                # There is NO separate episode folder - all episode files are in the Season folder
                #
                # recording_dir = Season folder (e.g., /recordings/GRONKH/Season 2026-01/)
                # We should ONLY delete the Season folder if it's completely empty (no other recordings)

                # Check if the Season directory is now completely empty (no other recordings remain)
                if recording_dir and os.path.exists(recording_dir):
                    try:
                        # Count remaining recordings in the Season folder
                        # Look for .mp4, .ts, .mkv files (actual recordings, not metadata)
                        recording_extensions = {".mp4", ".ts", ".mkv", ".avi", ".mov"}
                        remaining_recordings = []

                        for item in os.listdir(recording_dir):
                            item_path = os.path.join(recording_dir, item)

                            # Skip hidden files/dirs
                            if item.startswith("."):
                                continue

                            # Check if it's a recording file
                            if os.path.isfile(item_path):
                                _, ext = os.path.splitext(item.lower())
                                if ext in recording_extensions:
                                    remaining_recordings.append(item)

                            # Check if it's a segments directory (indicates active/incomplete recording)
                            elif os.path.isdir(item_path) and item.endswith(
                                "_segments"
                            ):
                                remaining_recordings.append(item)

                        if remaining_recordings:
                            # Other recordings still exist in this Season folder - keep it!
                            self._logger.debug(
                                f"Season directory {recording_dir} still has {len(remaining_recordings)} recordings, keeping it"
                            )
                        else:
                            # Season folder is truly empty of recordings - safe to delete
                            # But first check for any non-metadata files
                            metadata_files = {
                                "poster.jpg",
                                "fanart.jpg",
                                "season-poster.jpg",
                                "banner.jpg",
                                "season.nfo",
                                "tvshow.nfo",
                                "folder.jpg",
                            }

                            all_items = [
                                f
                                for f in os.listdir(recording_dir)
                                if not f.startswith(".")
                            ]
                            non_metadata_items = [
                                f for f in all_items if f.lower() not in metadata_files
                            ]

                            if not non_metadata_items:
                                # Only metadata files remain - safe to delete Season folder
                                # SECURITY: Validate path before deletion
                                try:
                                    safe_season_dir = self._validate_path(
                                        recording_dir, "delete"
                                    )
                                    shutil.rmtree(safe_season_dir)
                                    self._logger.info(
                                        f"🗂️ Removed empty Season directory: {safe_season_dir}"
                                    )

                                    # Now check if the Streamer folder is also empty
                                    streamer_dir = os.path.dirname(safe_season_dir)
                                    if os.path.exists(streamer_dir):
                                        streamer_items = [
                                            f
                                            for f in os.listdir(streamer_dir)
                                            if not f.startswith(".")
                                            and f.lower() not in metadata_files
                                        ]
                                        if not streamer_items:
                                            try:
                                                safe_streamer_dir = self._validate_path(
                                                    streamer_dir, "delete"
                                                )
                                                shutil.rmtree(safe_streamer_dir)
                                                self._logger.info(
                                                    f"🗂️ Removed empty Streamer directory: {safe_streamer_dir}"
                                                )
                                            except Exception as e:
                                                self._logger.debug(
                                                    f"Could not remove Streamer directory: {e}"
                                                )
                                except Exception as e:
                                    self._logger.warning(
                                        f"Could not remove Season directory {recording_dir}: {e}"
                                    )
                            else:
                                self._logger.debug(
                                    f"Season directory {recording_dir} has non-metadata items: {non_metadata_items[:5]}..."
                                )
                    except Exception as e:
                        self._logger.debug(
                            f"Could not check Season directory {recording_dir}: {e}"
                        )

            except Exception as e:
                self._logger.error(
                    f"Error deleting stream {stream.id}: {e}", exc_info=True
                )

        # Commit changes to the database
        db.commit()
        return deleted_count, deleted_paths

    def _get_storage_usage(self, streamer_id: int) -> Dict[str, Any]:
        """
        Get storage usage statistics for a streamer

        Args:
            streamer_id: ID of the streamer

        Returns:
            Dictionary with totalSize, recordingCount, oldestRecording, newestRecording
        """
        with self._session_factory() as db:
            try:
                # Get all recordings for this streamer
                streams = (
                    db.query(Stream)
                    .filter(
                        Stream.streamer_id == streamer_id,
                        Stream.recording_path.isnot(None),
                    )
                    .order_by(Stream.started_at)
                    .all()
                )

                total_size = 0
                oldest_recording = None
                newest_recording = None
                recording_count = 0

                for stream in streams:
                    if stream.recording_path and os.path.exists(stream.recording_path):
                        recording_count += 1

                        # Update oldest/newest
                        if stream.started_at:
                            if (
                                oldest_recording is None
                                or stream.started_at < oldest_recording
                            ):
                                oldest_recording = stream.started_at
                            if (
                                newest_recording is None
                                or stream.started_at > newest_recording
                            ):
                                newest_recording = stream.started_at

                        # Calculate file size
                        try:
                            file_size = os.path.getsize(stream.recording_path)
                            total_size += file_size
                        except Exception as e:
                            self._logger.error(
                                f"Error getting size for {stream.recording_path}: {e}"
                            )

                return {
                    "totalSize": total_size,
                    "recordingCount": recording_count,
                    "oldestRecording": oldest_recording.isoformat()
                    if oldest_recording
                    else "",
                    "newestRecording": newest_recording.isoformat()
                    if newest_recording
                    else "",
                }

            except Exception as e:
                self._logger.error(f"Error getting storage usage: {e}", exc_info=True)
                return {
                    "totalSize": 0,
                    "recordingCount": 0,
                    "oldestRecording": "",
                    "newestRecording": "",
                }

    def _run_scheduled_cleanup(self) -> None:
        """Run cleanup for all streamers with configured policies"""
        self._logger.info("Starting scheduled cleanup for all streamers")

        # Get all streamers with recording settings
        try:
            with self._session_factory() as db:
                streamers = db.query(Streamer).all()
                cleanup_count = 0
                total_deleted_count = 0
                processed_count = 0

                for streamer in streamers:
                    processed_count += 1
                    # Check if the streamer has a cleanup policy
                    try:
                        policy = self._get_effective_cleanup_policy(streamer.id, db)
                        if policy is None:
                            # No cleanup policy configured (max_streams=0 means unlimited)
                            self._logger.debug(
                                f"Skipping streamer {streamer.username} ({processed_count}/{len(streamers)}) "
                                f"- no cleanup policy (unlimited retention)"
                            )
                            continue

                        self._logger.info(
                            f"Processing streamer {streamer.username} ({processed_count}/{len(streamers)}) "
                            f"with policy {policy.type.value} (threshold: {policy.threshold})"
                        )

                        # Get current storage stats before cleanup
                        storage_before = self._get_storage_usage(streamer.id)

                        # Run the cleanup
                        (
                            deleted_count,
                            deleted_paths,
                        ) = self._cleanup_old_recordings(streamer.id, db)

                        if deleted_count > 0:
                            # Get storage stats after cleanup
                            storage_after = self._get_storage_usage(streamer.id)
                            freed_space = (
                                storage_before["totalSize"] - storage_after["totalSize"]
                            )
                            freed_space_mb = freed_space / (
                                1024 * 1024
                            )  # Convert to MB

                            self._logger.info(
                                f"Cleaned up {deleted_count} recordings for streamer {streamer.username}, "
                                f"freed {freed_space_mb:.2f} MB of space"
                            )

                            cleanup_count += 1
                            total_deleted_count += deleted_count
                        else:
                            self._logger.debug(
                                f"No recordings to clean up for streamer {streamer.username}"
                            )
                    except InvalidRetentionPolicy as error:
                        self._logger.warning(
                            "Skipping retention for channel %s: %s", streamer.id, error
                        )
                    except Exception as e:
                        self._logger.error(
                            f"Error during cleanup for streamer {streamer.username}: {e}",
                            exc_info=True,
                        )

                self._logger.info(
                    f"Scheduled cleanup completed for {cleanup_count}/{len(streamers)} streamers. "
                    f"Deleted {total_deleted_count} recordings in total."
                )
        except Exception as e:
            self._logger.error(f"Error during scheduled cleanup: {e}", exc_info=True)

    def _simulate_cleanup(
        self,
        streamer_id: int,
        db: Optional[Session] = None,
        custom_policy: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, dict[str, object] | list[dict[str, object]]]:
        """
        Simulate cleanup based on the streamer's cleanup policy without actually deleting files

        Args:
            streamer_id: ID of the streamer
            db: Database session
            custom_policy: Override the stored policy with this one

        Returns:
            Tuple containing (number of recordings that would be deleted, list of stream details)
        """
        close_db = False
        if db is None:
            db = self._session_factory()
            close_db = True

        try:
            policy = self._resolve_policy(streamer_id, db, custom_policy)
            if policy is None:
                return 0, []
            streams = self._select_streams(streamer_id, db, policy)

            # Format the result for display
            result_streams = []
            total_size = 0

            for stream in streams:
                size = 0
                if stream.recording_path and os.path.exists(stream.recording_path):
                    try:
                        size = os.path.getsize(stream.recording_path)
                        total_size += size
                    except Exception:
                        # Ignore permission errors or race conditions where file was deleted
                        pass

                result_streams.append(
                    {
                        "id": stream.id,
                        "title": stream.title,
                        "category": getattr(stream, "category_name", "Unknown"),
                        "started_at": stream.started_at.isoformat()
                        if stream.started_at
                        else None,
                        "path": stream.recording_path,
                        "size": size,
                        "size_formatted": self._format_size(size),
                    }
                )

            return (
                len(result_streams),
                {
                    "streams": result_streams,
                    "total_size": total_size,
                    "total_size_formatted": self._format_size(total_size),
                    "policy": {
                        "type": policy.type.value,
                        "threshold": policy.threshold,
                        "preserve_favorites": policy.preserve_favorites,
                        "preserve_categories": policy.preserve_categories or [],
                    },
                },
            )

        except InvalidRetentionPolicy:
            raise
        except Exception as e:
            self._logger.error(f"Error simulating cleanup: {e}", exc_info=True)
            return 0, {
                "streams": [],
                "total_size": 0,
                "total_size_formatted": "0 B",
                "policy": {},
            }
        finally:
            if close_db:
                db.close()

    def _format_size(self, size_bytes: int) -> str:
        """Format a size in bytes to a human-readable string"""
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"

    def _cleanup_orphaned_files(
        self,
        recordings_root: Optional[str] = None,
    ) -> Tuple[int, List[str]]:
        """
        🧹 Cleanup Orphaned Files
        Remove broken symlinks, 0-byte files, and empty segment directories

        **SECURITY**: Uses path validation to prevent traversal attacks.

        Args:
            recordings_root: Optional root directory. If None, uses configured RECORDING_DIRECTORY.
        """
        # Use configured directory if none provided (safest approach)
        if recordings_root is None:
            recordings_root = (self._settings or get_settings()).RECORDING_DIRECTORY

        # Type narrowing: at this point recordings_root is definitely str
        if not isinstance(recordings_root, str):
            raise TypeError("recordings_root must be a string")

        # SECURITY: Always validate user-provided paths
        # Directory traversal needs containment, not the file-only read validator.
        safe_root = self._validate_path(recordings_root, "access")

        self._logger.info(f"🧹 CLEANUP_ORPHANED_FILES: Starting cleanup in {safe_root}")

        cleaned_paths = []
        cleaned_count = 0

        try:
            # Helper function to validate paths during traversal
            # Uses shared validation logic from security module
            def is_safe_subpath(path: str) -> bool:
                """Validate that a path is within safe_root (defense-in-depth)"""
                try:
                    real_path = os.path.realpath(path)
                    real_safe_root = os.path.realpath(safe_root)
                    return is_path_within_base(real_path, real_safe_root)
                except OSError, ValueError:
                    return False

            for root, dirs, files in os.walk(safe_root):
                # Check for broken symlinks and 0-byte files
                for filename in files:
                    file_path = os.path.join(root, filename)

                    try:
                        # SECURITY: Defense-in-depth - validate sub-path
                        if not is_safe_subpath(file_path):
                            self._logger.warning(
                                f"🚨 SECURITY: Skipping file outside safe root: {file_path}"
                            )
                            continue

                        # Check for broken symlinks
                        if os.path.islink(file_path):
                            if not os.path.exists(file_path):
                                os.unlink(file_path)
                                cleaned_paths.append(file_path)
                                cleaned_count += 1
                                self._logger.info(
                                    f"🧹 Removed broken symlink: {file_path}"
                                )
                                continue

                        # Check for 0-byte NFO files (excluding tvshow.nfo and season.nfo which can be small)
                        if filename.endswith(".nfo") and filename not in [
                            "tvshow.nfo",
                            "season.nfo",
                        ]:
                            if (
                                os.path.exists(file_path)
                                and os.path.getsize(file_path) == 0
                            ):
                                os.remove(file_path)
                                cleaned_paths.append(file_path)
                                cleaned_count += 1
                                self._logger.info(
                                    f"🧹 Removed 0-byte NFO file: {file_path}"
                                )

                    except Exception as e:
                        self._logger.debug(f"Error processing file {file_path}: {e}")

                # Check for empty segment directories
                for dirname in dirs[
                    :
                ]:  # Use slice copy to allow modification during iteration
                    if dirname.endswith("_segments"):
                        dir_path = os.path.join(root, dirname)
                        try:
                            # SECURITY: Defense-in-depth - validate sub-path
                            if not is_safe_subpath(dir_path):
                                self._logger.warning(
                                    f"🚨 SECURITY: Skipping directory outside safe root: {dir_path}"
                                )
                                continue

                            if os.path.isdir(dir_path):
                                # Check if directory is empty
                                if not os.listdir(dir_path):
                                    os.rmdir(dir_path)
                                    cleaned_count += 1
                                    self._logger.info(
                                        f"🧹 Removed empty segment directory: {dir_path}"
                                    )
                        except Exception as e:
                            self._logger.debug(
                                f"Error processing directory {dir_path}: {e}"
                            )

            self._logger.info(
                f"🧹 Orphaned files cleanup completed: {cleaned_count} items cleaned"
            )
            return cleaned_count, cleaned_paths

        except Exception as e:
            self._logger.error(
                f"Error during orphaned files cleanup: {e}", exc_info=True
            )
            return cleaned_count, cleaned_paths


# Global cleanup service instance
cleanup_service = CleanupService()
