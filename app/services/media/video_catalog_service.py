import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
from sqlalchemy import and_, event, exists, func, inspect, or_, select, update
from sqlalchemy.orm import Session
from app.models import (
    Stream,
    Streamer,
    Recording,
    ActiveRecordingState,
    StreamMetadata,
    VideoCatalogEntry,
)

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

    @staticmethod
    @contextmanager
    def track_changes():
        """Install lifecycle-scoped transactional invalidation after migrations."""

        def invalidate(session, _context):
            ids = set()
            relevant_fields = {
                Stream: (
                    "recording_path",
                    "started_at",
                    "ended_at",
                    "title",
                    "category_name",
                    "language",
                    "streamer_id",
                ),
                Recording: ("path", "status", "start_time", "end_time", "stream_id"),
                ActiveRecordingState: (
                    "ts_output_path",
                    "status",
                    "started_at",
                    "stream_id",
                    "recording_id",
                ),
                StreamMetadata: ("thumbnail_path", "thumbnail_url"),
            }
            for item in session.new | session.dirty | session.deleted:
                fields = relevant_fields.get(type(item))
                if fields is None:
                    continue
                if item in session.dirty and not any(
                    inspect(item).attrs[field].history.has_changes() for field in fields
                ):
                    continue
                ids.add(item.id if isinstance(item, Stream) else item.stream_id)
            ids.discard(None)
            if ids:
                connection = session.connection()
                connection.execute(
                    update(VideoCatalogEntry.__table__)
                    .where(VideoCatalogEntry.stream_id.in_(ids))
                    .values(dirty=True, revision=VideoCatalogEntry.revision + 1)
                )
                # New candidates behind the discovery cursor need the same priority path.
                if connection.dialect.name == "postgresql":
                    from sqlalchemy.dialects.postgresql import insert
                else:
                    from sqlalchemy.dialects.sqlite import insert

                connection.execute(
                    insert(VideoCatalogEntry.__table__)
                    .from_select(
                        ["stream_id"],
                        select(Stream.id).where(
                            Stream.id.in_(ids),
                            VideoCatalogService._catalog_candidates(),
                        ),
                    )
                    .on_conflict_do_nothing(index_elements=["stream_id"])
                )

        event.listen(Session, "after_flush", invalidate)
        try:
            yield
        finally:
            event.remove(Session, "after_flush", invalidate)

    @staticmethod
    def _catalog_candidates():
        return or_(
            and_(Stream.recording_path.isnot(None), Stream.recording_path != ""),
            exists().where(
                and_(
                    Recording.stream_id == Stream.id,
                    Recording.status.in_(("completed", "post_processing")),
                    Recording.path.isnot(None),
                    Recording.path != "",
                )
            ),
            exists().where(
                and_(
                    ActiveRecordingState.stream_id == Stream.id,
                    ActiveRecordingState.status == "active",
                )
            ),
        )

    @staticmethod
    def _catalog_utc(value):
        return (
            value.replace(tzinfo=timezone.utc)
            if value and value.tzinfo is None
            else value
        )

    def reconcile_next_batch(self, cursor: int = 0) -> tuple[int, int]:
        pending = (
            self.db.query(VideoCatalogEntry.stream_id)
            .join(Stream, Stream.id == VideoCatalogEntry.stream_id)
            .filter(
                or_(
                    VideoCatalogEntry.state == "pending",
                    VideoCatalogEntry.dirty.is_(True),
                )
            )
            .order_by(VideoCatalogEntry.stream_id)
            .limit(200)
            .all()
        )
        if pending:
            last, count = self.reconcile_batch(stream_ids=[item[0] for item in pending])
            return cursor, count
        return self.reconcile_batch(after_id=cursor)

    def reconcile_batch(
        self,
        *,
        after_id: int = 0,
        limit: int = 200,
        stream_ids: list[int] | None = None,
    ) -> tuple[int, int]:
        """Bounded worker-only filesystem snapshot; never repair authoritative paths."""
        if not 1 <= limit <= 1000:
            raise ValueError("catalog reconciliation batch must be between 1 and 1000")
        streams = (
            self.db.query(Stream)
            .outerjoin(VideoCatalogEntry, VideoCatalogEntry.stream_id == Stream.id)
            .filter(
                Stream.id > after_id,
                or_(
                    self._catalog_candidates(), VideoCatalogEntry.stream_id.isnot(None)
                ),
            )
            .filter(Stream.id.in_(stream_ids) if stream_ids is not None else True)
            .order_by(Stream.id)
            .limit(limit)
            .all()
        )
        if not streams:
            return 0, 0
        ids = [stream.id for stream in streams]
        entries = {
            entry.stream_id: entry
            for entry in self.db.query(VideoCatalogEntry)
            .filter(VideoCatalogEntry.stream_id.in_(ids))
            .all()
        }
        recordings = {}
        for item in (
            self.db.query(Recording)
            .filter(
                Recording.stream_id.in_(ids),
                Recording.status.in_(("completed", "post_processing")),
            )
            .order_by(Recording.start_time.desc(), Recording.id.desc())
            .all()
        ):
            recordings.setdefault(item.stream_id, []).append(item)
        active = {}
        for item in (
            self.db.query(ActiveRecordingState)
            .filter(
                ActiveRecordingState.stream_id.in_(ids),
                ActiveRecordingState.status == "active",
            )
            .order_by(ActiveRecordingState.id.desc())
            .all()
        ):
            active.setdefault(item.stream_id, item)
        now = datetime.now(timezone.utc)
        freshness = []
        for stream in streams:
            entry = entries.get(stream.id)
            if entry is None:
                entry = VideoCatalogEntry(stream_id=stream.id)
                self.db.add(entry)
            entry.file_path = None
            entry.file_size = 0
            entry.duration = None
            entry.started_at = stream.started_at
            entry.ended_at = stream.ended_at
            entry.recording_id = None
            entry.is_recording = stream.id in active
            entry.has_thumbnail = False
            entry.error_type = None
            entry.dirty = False
            entry.state = (
                "missing"
                if stream.recording_path
                or recordings.get(stream.id)
                or entry.is_recording
                else "excluded"
            )
            try:
                candidates = []
                if stream.recording_path:
                    candidates.append((Path(stream.recording_path), None))
                for recording in recordings.get(stream.id, []):
                    if recording.path:
                        path = Path(recording.path)
                        candidates.extend(
                            ((path.with_suffix(".mp4"), recording), (path, recording))
                        )
                for path, recording in candidates:
                    try:
                        stats = path.stat()
                    except FileNotFoundError:
                        continue
                    import stat

                    if not stat.S_ISREG(stats.st_mode):
                        continue
                    entry.file_path = str(path)
                    entry.file_size = stats.st_size
                    entry.state = "active" if entry.is_recording else "available"
                    if recording:
                        entry.recording_id = recording.id
                        entry.started_at = recording.start_time or stream.started_at
                        entry.ended_at = recording.end_time or stream.ended_at
                    break
                state = active.get(stream.id)
                if state:
                    if not entry.file_path:
                        entry.file_path = state.ts_output_path
                        if state.ts_output_path:
                            try:
                                entry.file_size = (
                                    Path(state.ts_output_path).stat().st_size
                                )
                            except FileNotFoundError:
                                pass
                    entry.state = "active"
                    entry.started_at = state.started_at or stream.started_at
                    entry.ended_at = None
                    entry.recording_id = state.recording_id
                started = self._catalog_utc(entry.started_at)
                ended = self._catalog_utc(entry.ended_at)
                if started:
                    entry.duration = (
                        max(
                            0,
                            (
                                (now if entry.is_recording else ended) - started
                            ).total_seconds(),
                        )
                        if entry.is_recording or ended
                        else None
                    )
                if entry.file_path:
                    entry.has_thumbnail = (
                        get_video_thumbnail_url(stream.id, entry.file_path) is not None
                    )
            except OSError as error:
                entry.state = "error"
                entry.error_type = type(error).__name__
            if entry in self.db.new or self.db.is_modified(entry):
                entry.checked_at = now
            else:
                freshness.append((entry.stream_id, entry.revision))
        if freshness:
            from sqlalchemy import tuple_, update
            from sqlalchemy.orm.exc import StaleDataError

            result = self.db.execute(
                update(VideoCatalogEntry)
                .where(
                    tuple_(VideoCatalogEntry.stream_id, VideoCatalogEntry.revision).in_(
                        freshness
                    )
                )
                .values(checked_at=now),
                execution_options={"synchronize_session": False},
            )
            if result.rowcount != len(freshness):
                raise StaleDataError("Catalog source changed during freshness update")
        self.db.commit()
        return streams[-1].id, len(streams)

    def list_page(
        self,
        *,
        page=1,
        page_size=50,
        q=None,
        streamer_id=None,
        streamer=None,
        category=None,
        recording=None,
        sort="date",
        order=None,
        created_from=None,
        created_before=None,
        duration=None,
        stream_id=None,
        _refilled=False,
    ):
        """SQL-filtered snapshot page; filesystem cost is bounded by page size."""
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("invalid catalog page")
        sort_columns = {
            "date": VideoCatalogEntry.started_at,
            "title": func.lower(Stream.title),
            "streamer": func.lower(Streamer.username),
            "duration": VideoCatalogEntry.duration,
            "size": VideoCatalogEntry.file_size,
        }
        if sort not in sort_columns or order not in (None, "asc", "desc"):
            raise ValueError("invalid catalog sort")
        base = (
            self.db.query(VideoCatalogEntry, Stream, Streamer)
            .join(Stream, Stream.id == VideoCatalogEntry.stream_id)
            .join(Streamer, Streamer.id == Stream.streamer_id)
            .filter(VideoCatalogEntry.state.in_(("available", "active")))
        )
        filtered = base
        if q:
            literal = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filtered = filtered.filter(
                or_(
                    Stream.title.ilike(f"%{literal}%", escape="\\"),
                    Streamer.username.ilike(f"%{literal}%", escape="\\"),
                )
            )
        if streamer_id is not None:
            filtered = filtered.filter(Streamer.id == streamer_id)
        if streamer is not None:
            filtered = filtered.filter(Streamer.username == streamer)
        if stream_id is not None:
            filtered = filtered.filter(Stream.id == stream_id)
        if category is not None:
            filtered = filtered.filter(Stream.category_name == category)
        if recording is not None:
            filtered = filtered.filter(VideoCatalogEntry.is_recording == recording)
        if created_from is not None:
            filtered = filtered.filter(VideoCatalogEntry.started_at >= created_from)
        if created_before is not None:
            filtered = filtered.filter(VideoCatalogEntry.started_at < created_before)
        seconds = func.coalesce(VideoCatalogEntry.duration, 0)
        if duration == "short":
            filtered = filtered.filter(seconds < 3600)
        elif duration == "medium":
            filtered = filtered.filter(seconds >= 3600, seconds <= 10800)
        elif duration == "long":
            filtered = filtered.filter(seconds > 10800)
        elif duration is not None:
            raise ValueError("invalid duration filter")
        column = sort_columns[sort]
        descending = order == "desc" if order else sort not in ("title", "streamer")
        ordered = filtered.order_by(
            (column.desc() if descending else column.asc()).nulls_last(),
            Stream.id.asc(),
        )
        rows = ordered.limit(page_size).offset((page - 1) * page_size).all()
        items = []
        changed = False
        now = datetime.now(timezone.utc)
        for entry, stream, row_streamer in rows:
            size = entry.file_size
            seconds = entry.duration
            if entry.is_recording:
                if entry.file_path:
                    try:
                        size = Path(entry.file_path).stat().st_size
                    except FileNotFoundError:
                        size = 0
                started = self._catalog_utc(entry.started_at)
                seconds = max(0, (now - started).total_seconds()) if started else None
            elif entry.file_path:
                try:
                    stats = Path(entry.file_path).stat()
                    size = stats.st_size
                except FileNotFoundError:
                    entry.state = "missing"
                    changed = True
                    continue
                except OSError as error:
                    entry.state = "error"
                    entry.error_type = type(error).__name__
                    changed = True
                    continue
            items.append(
                {
                    "id": stream.id,
                    "title": stream.title or f"Stream {stream.id}",
                    "streamer_name": row_streamer.username,
                    "streamer_id": row_streamer.id,
                    "file_path": entry.file_path,
                    "file_size": size,
                    "created_at": entry.started_at.isoformat()
                    if entry.started_at
                    else None,
                    "started_at": entry.started_at.isoformat()
                    if entry.started_at
                    else None,
                    "ended_at": entry.ended_at.isoformat() if entry.ended_at else None,
                    "duration": seconds,
                    "category_name": stream.category_name,
                    "language": stream.language,
                    "thumbnail_url": f"/api/videos/{stream.id}/thumbnail"
                    if entry.has_thumbnail
                    else None,
                    "has_thumbnail": entry.has_thumbnail,
                    "is_recording": entry.is_recording,
                    "recording_id": entry.recording_id,
                }
            )
        if changed:
            self.db.commit()
            if not _refilled:
                result = self.list_page(
                    page=page,
                    page_size=page_size,
                    q=q,
                    streamer_id=streamer_id,
                    streamer=streamer,
                    category=category,
                    recording=recording,
                    sort=sort,
                    order=order,
                    created_from=created_from,
                    created_before=created_before,
                    duration=duration,
                    stream_id=stream_id,
                    _refilled=True,
                )
                result["index"]["page_revalidation_changed"] = True
                return result
        total = filtered.order_by(None).count()
        summary = base.with_entities(
            func.count(Stream.id),
            func.coalesce(func.sum(VideoCatalogEntry.file_size), 0),
            func.coalesce(func.sum(VideoCatalogEntry.duration), 0),
        ).one()
        facets = (
            base.with_entities(Streamer.id, Streamer.username, func.count(Stream.id))
            .group_by(Streamer.id, Streamer.username)
            .order_by(Streamer.username, Streamer.id)
            .all()
        )
        categories = (
            base.with_entities(Stream.category_name)
            .filter(Stream.category_name.isnot(None))
            .distinct()
            .order_by(Stream.category_name)
            .all()
        )
        index_query = (
            self.db.query(Stream)
            .outerjoin(VideoCatalogEntry, VideoCatalogEntry.stream_id == Stream.id)
            .filter(self._catalog_candidates())
        )
        index = {
            "pending": index_query.filter(
                or_(
                    VideoCatalogEntry.stream_id.is_(None),
                    VideoCatalogEntry.state.in_(("pending", "excluded")),
                    VideoCatalogEntry.dirty.is_(True),
                )
            ).count()
        }
        for state in ("missing", "error"):
            index[state] = index_query.filter(VideoCatalogEntry.state == state).count()
        oldest = self.db.query(func.min(VideoCatalogEntry.checked_at)).scalar()
        index["oldest_checked_at"] = oldest.isoformat() if oldest else None
        index["complete"] = (
            index["pending"] == 0 and index["error"] == 0 and not changed
        )
        index["page_revalidation_changed"] = changed
        index["retry_required"] = changed
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": page * page_size < total,
            "index": index,
            "summary": {
                "total": summary[0],
                "file_size": summary[1],
                "duration": summary[2],
                "streamers": [
                    {"id": item[0], "name": item[1], "count": item[2]}
                    for item in facets
                ],
                "categories": [item[0] for item in categories],
            },
        }

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
                        # SQLite reloads timezone-aware columns as naive UTC.
                        started_utc = (
                            started.replace(tzinfo=timezone.utc)
                            if started.tzinfo is None
                            else started.astimezone(timezone.utc)
                        )
                        duration = (
                            datetime.now(timezone.utc) - started_utc
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
