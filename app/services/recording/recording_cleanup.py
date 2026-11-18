"""Resolve cleanup from the catalog; never grant deletion authority to job paths."""

import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActiveRecordingState, Recording, Stream, StreamMetadata
from app.services.recording.file_operations import _check_ffmpeg_processes_for_file


class CleanupRef(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stream_id: Annotated[int, Field(gt=0)]
    recording_id: Annotated[int, Field(gt=0)] | None = None
    mode: Literal["post_processing", "artifacts"] = "post_processing"


class CleanupRefused(ValueError):
    pass


EPISODE_FIELDS = (
    "thumbnail_path",
    "nfo_path",
    "json_path",
    "chapters_vtt_path",
    "chapters_srt_path",
    "chapters_ffmpeg_path",
    "chapters_xml_path",
)
SHARED_FIELDS = ("tvshow_nfo_path", "season_nfo_path")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _path(root: Path, raw: str) -> Path:
    path = Path(raw)
    if ".." in path.parts or "\0" in raw:
        raise CleanupRefused("Invalid recording path")
    if not path.is_absolute():
        path = root / path
    if path == root or not path.is_relative_to(root):
        raise CleanupRefused("Invalid recording path")
    return path


@contextmanager
def _parent(root: Path, path: Path) -> Iterator[tuple[int, str, list[tuple[int, int]]]]:
    # Open every component without following symlinks, including the root's parents.
    if root == Path(root.anchor) or ".." in root.parts:
        raise CleanupRefused("Invalid recordings root")
    parts = path.relative_to(root).parts
    fd = os.open(root.anchor, DIR_FLAGS)
    identities = []
    try:
        for index, part in enumerate((*root.parts[1:], *parts[:-1])):
            child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
            if index >= len(root.parts) - 2:
                item = os.fstat(fd)
                identities.append((item.st_dev, item.st_ino))
        yield fd, parts[-1], identities
    finally:
        os.close(fd)


def _regular(fd: int, name: str) -> os.stat_result:
    item = os.stat(name, dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISREG(item.st_mode) or item.st_nlink != 1:
        raise CleanupRefused("Recording file is not an exclusive regular file")
    return item


def _entry_identity(item: os.stat_result) -> list[int]:
    return [item.st_dev, item.st_ino, item.st_ctime_ns]


def _unchanged(
    item: os.stat_result, ancestors: list[tuple[int, int]], expected: list[list[int]]
) -> None:
    if [*[list(identity) for identity in ancestors], _entry_identity(item)] != expected:
        raise CleanupRefused("Recording target changed before removal")


def _remove_file(root: Path, path: Path, expected: list[list[int]]) -> int:
    try:
        with _parent(root, path) as (fd, name, ancestors):
            _unchanged(_regular(fd, name), ancestors, expected)
            os.unlink(name, dir_fd=fd)
            return 1
    except FileNotFoundError:
        return 0


def _remove_segments(
    root: Path, path: Path, stem: str, expected: list[list[int]]
) -> int:
    try:
        with _parent(root, path) as (fd, name, ancestors):
            segments = os.open(name, DIR_FLAGS, dir_fd=fd)
            try:
                directory = os.fstat(segments)
                _unchanged(directory, ancestors, expected)
                if directory.st_dev != os.fstat(fd).st_dev:
                    raise CleanupRefused("Segment directory crosses a mount boundary")
                names = os.listdir(segments)
                seen = {}
                for entry in names:
                    if not re.fullmatch(re.escape(stem) + r"_part[0-9]{3,}\.ts", entry):
                        raise CleanupRefused(
                            "Segment directory contains unowned entries"
                        )
                    seen[entry] = _entry_identity(_regular(segments, entry))
                for entry in names:
                    if _entry_identity(_regular(segments, entry)) != seen[entry]:
                        raise CleanupRefused("Segment changed before removal")
                    os.unlink(entry, dir_fd=segments)
                current = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not os.path.samestat(current, os.fstat(segments)):
                    raise CleanupRefused("Segment directory changed during cleanup")
                os.rmdir(name, dir_fd=fd)
                return 1
            finally:
                os.close(segments)
    except FileNotFoundError:
        return 0


def _catalog(
    db: Session, ref: CleanupRef, *, lock: bool = False
) -> tuple[Stream, list[Recording]]:
    stream = db.get(Stream, ref.stream_id, with_for_update=lock)
    if stream is None:
        raise CleanupRefused("Unknown stream")
    rows = select(Recording).where(Recording.stream_id == stream.id)
    recordings = list(db.scalars(rows.with_for_update() if lock else rows))
    if ref.recording_id is not None and not any(
        row.id == ref.recording_id for row in recordings
    ):
        raise CleanupRefused("Recording does not belong to stream")
    if any(row.status == "recording" for row in recordings):
        raise CleanupRefused("Recording is still active")
    if (
        db.scalar(
            select(ActiveRecordingState.id).where(
                ActiveRecordingState.stream_id == stream.id
            )
        )
        is not None
    ):
        raise CleanupRefused("Recording still has a capture owner")
    return stream, recordings


def _protected_paths(
    db: Session, root: Path, stream_id: int, recording_ids: set[int], *, explicit: bool
) -> set[Path]:
    paths = set(db.scalars(select(Stream.recording_path).where(Stream.id != stream_id)))
    paths.update(
        db.scalars(select(Recording.path).where(Recording.id.not_in(recording_ids)))
    )
    paths.update(db.scalars(select(ActiveRecordingState.ts_output_path)))
    for row in db.scalars(select(StreamMetadata)):
        for key in SHARED_FIELDS:
            paths.add(getattr(row, key))
        if row.stream_id != stream_id:
            for key in (*EPISODE_FIELDS, "segments_dir_path"):
                paths.add(getattr(row, key))
        elif not explicit:
            for key in EPISODE_FIELDS:
                paths.add(getattr(row, key))
    protected = set()
    for raw in paths - {None, ""}:
        path = root / raw
        protected.update((path, path.resolve()))
    return protected


def _assert_exclusive(path: Path, protected: set[Path]) -> None:
    if any(
        path.is_relative_to(other) or other.is_relative_to(path) for other in protected
    ):
        raise CleanupRefused(
            "Recording target has shared or foreign catalog references"
        )


def _sources(output: Path) -> tuple[Path, Path]:
    return output.with_suffix(".ts"), output.with_name(f"{output.stem}_segments")


def _plan(
    db: Session, root: Path, ref: CleanupRef, *, lock: bool = False
) -> tuple[Path, set[Path]]:
    stream, recordings = _catalog(db, ref, lock=lock)
    selected = [row for row in recordings if ref.recording_id in (None, row.id)]
    if len(selected) > 1:
        raise CleanupRefused("Select one recording for cleanup")
    local = selected[0].path if selected else None
    if not local and not stream.recording_path:
        raise CleanupRefused("Recording has no catalog media")
    primary = _path(root, local or stream.recording_path or "")
    if primary.suffix not in {".ts", ".mp4"}:
        raise CleanupRefused("Recording has no recognized media")
    output = primary.with_suffix(".mp4")
    stream_path = _path(root, stream.recording_path) if stream.recording_path else None
    # A sibling MP4 is not proof that remux replaced a catalogued TS.
    if output not in {primary, stream_path}:
        raise CleanupRefused(
            "MP4 file not found in the recording catalog, not removing source files"
        )
    source, segments = _sources(output)
    targets = {source, segments} - {stream_path}
    protected = _protected_paths(
        db, root, stream.id, {r.id for r in selected}, explicit=False
    )
    for target in {*targets, output}:
        _assert_exclusive(target, protected)
    return output, targets


def _identity(root: Path, path: Path) -> list[list[int]]:
    with _parent(root, path) as (fd, name, ancestors):
        result = [list(item) for item in ancestors]
        try:
            item = os.stat(name, dir_fd=fd, follow_symlinks=False)
        except FileNotFoundError:
            return result
        if stat.S_ISLNK(item.st_mode):
            raise CleanupRefused("Symbolic links cannot be cleanup targets")
        return [*result, _entry_identity(item)]


def _snapshot(
    root: Path, output: Path, targets: set[Path]
) -> dict[str, list[list[int]]]:
    return {
        str(path.relative_to(root)): _identity(root, path)
        for path in {output, *targets}
    }


def admit_cleanup(db: Session, root: Path, ref: CleanupRef) -> dict[str, Any]:
    root = root.absolute()
    output, targets = _plan(db, root, ref)
    return {**ref.model_dump(), "cleanup_snapshot": _snapshot(root, output, targets)}


def clean_recording(db: Session, root: Path, payload: dict[str, Any]) -> list[Path]:
    root = root.absolute()
    raw = dict(payload)
    raw.pop("task_id", None)
    snapshot = raw.pop("cleanup_snapshot", None)
    has_legacy_paths = "cleanup_paths" in raw or "files_to_remove" in raw
    legacy = raw.pop("cleanup_paths", raw.pop("files_to_remove", None))
    legacy_output = raw.pop("mp4_path", None)
    if "cleanup_paths" in payload:
        if "files_to_remove" in payload or "mp4_path" in payload:
            raise CleanupRefused("Conflicting cleanup modes")
        raw.setdefault("mode", "artifacts")
    wait = raw.pop("max_wait_time", None)
    intelligent = raw.pop("intelligent_cleanup", False)
    if type(intelligent) is not bool or (
        wait is not None and (type(wait) is not int or not 0 <= wait <= 1800)
    ):
        raise CleanupRefused("Invalid legacy cleanup options")
    for key in (
        "streamer_name",
        "started_at",
        "output_dir",
        "ts_file_path",
        "directories_to_check",
    ):
        raw.pop(key, None)
    ref = CleanupRef.model_validate(raw)
    if db.get_bind().dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    output, permitted = _plan(db, root, ref, lock=True)
    if legacy_output is not None and (
        type(legacy_output) is not str or _path(root, legacy_output) != output
    ):
        raise CleanupRefused("MP4 does not belong to recording")
    targets = permitted
    if has_legacy_paths:
        if not isinstance(legacy, list) or not all(
            type(path) is str for path in legacy
        ):
            raise CleanupRefused("Invalid legacy cleanup selection")
        targets = {_path(root, path) for path in legacy}
        if not targets <= permitted:
            raise CleanupRefused(
                "Cleanup target does not belong to recording artifacts"
            )
    current = _snapshot(root, output, permitted)
    if snapshot is not None and snapshot != current:
        raise CleanupRefused("Recording files changed after cleanup admission")
    try:
        with _parent(root, output) as (fd, name, ancestors):
            item = _regular(fd, name)
            _unchanged(item, ancestors, current[str(output.relative_to(root))])
            size = item.st_size
    except FileNotFoundError as error:
        raise CleanupRefused("MP4 file not found, not removing source files") from error
    if size < 1024 * 1024:
        raise CleanupRefused("MP4 file too small, not removing source files")
    source, segments = _sources(output)
    if intelligent and wait == 0:
        targets = targets - {source}
    if targets and _check_ffmpeg_processes_for_file(str(source), str(output)):
        raise CleanupRefused("Recording files are still in use")
    removed_segments = []
    if segments in targets and _remove_segments(
        root, segments, output.stem, current[str(segments.relative_to(root))]
    ):
        removed_segments.append(segments)
    if source in targets:
        _remove_file(root, source, current[str(source.relative_to(root))])
    return removed_segments


def delete_stream_files(db: Session, root: Path, stream_id: int) -> list[Path]:
    """Explicit DELETE only, while its authoritative catalog information still exists."""
    root = root.absolute()
    stream, recordings = _catalog(db, CleanupRef(stream_id=stream_id), lock=True)
    protected = _protected_paths(
        db, root, stream.id, {r.id for r in recordings}, explicit=True
    )
    media = {
        _path(root, raw)
        for raw in [stream.recording_path, *(r.path for r in recordings)]
        if raw
    }
    if any(path.suffix not in {".mp4", ".ts"} for path in media):
        raise CleanupRefused("Unrecognized catalog media")
    files = set(media)
    segments = {}
    for path in media:
        source, directory = _sources(path)
        if path.suffix == ".mp4":
            files.add(source)
        segments[directory] = path.stem
    for metadata in db.scalars(
        select(StreamMetadata).where(StreamMetadata.stream_id == stream.id)
    ):
        for key in EPISODE_FIELDS:
            if raw := getattr(metadata, key):
                path = _path(root, raw)
                if any(
                    path.parent == anchor.parent
                    and path.name
                    in {
                        anchor.stem + suffix
                        for suffix in (
                            ".nfo",
                            ".info.json",
                            ".json",
                            ".jpg",
                            "-thumb.jpg",
                            "_thumbnail.jpg",
                            ".vtt",
                            ".srt",
                            "-ffmpeg-chapters.txt",
                            ".xml",
                        )
                    }
                    for anchor in media
                ):
                    files.add(path)
    for path in {*files, *segments}:
        _assert_exclusive(path, protected)
    expected = {path: _identity(root, path) for path in {*files, *segments}}
    removed = [
        path
        for path, stem in sorted(segments.items())
        if _remove_segments(root, path, stem, expected[path])
    ]
    removed.extend(
        path for path in sorted(files) if _remove_file(root, path, expected[path])
    )
    return removed
