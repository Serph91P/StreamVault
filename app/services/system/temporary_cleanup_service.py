"""Conservative admin cleanup: media belongs to recovery/retention, not temp cleanup."""

import asyncio
import os
import stat
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Recording, Stream, Streamer, TwitchUpstreamLease
from app.services.recording.media_ownership import (
    CaptureState,
    LocalCapture,
    physical_state,
)
from app.services.twitch_upstream_coordinator import TwitchUpstreamCoordinator

MAX_CANDIDATES = 100
MIN_AGE_SECONDS = 24 * 3600


class TemporaryFileCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str = Field(min_length=1, max_length=4096)
    # JSON numeric identifiers lose precision in browsers above 2**53.
    device: str = Field(pattern=r"^[0-9]{1,20}$")
    inode: str = Field(pattern=r"^[0-9]{1,20}$")
    size: str = Field(pattern=r"^[0-9]{1,20}$")
    mtime_ns: str = Field(pattern=r"^[0-9]{1,20}$")


class TemporaryCleanupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dry_run: StrictBool = True
    confirmed: StrictBool = False
    candidates: list[TemporaryFileCandidate] = Field(
        default_factory=list, max_length=MAX_CANDIDATES
    )


def _is_disposable_name(path: Path) -> bool:
    if any(part.lower().endswith("_segments") for part in path.parts):
        return False
    if path.name.endswith(".tmp"):
        return not any(
            suffix.lower() in {".ts", ".mp4", ".mkv", ".webm", ".h264", ".aac", ".part"}
            for suffix in path.suffixes[:-1]
        )
    return path.match("streamlink_*.log.*") or path.match("ffmpeg_*.log.*")


def _snapshot(root: Path, path: Path) -> TemporaryFileCandidate | None:
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or time.time() - info.st_mtime < MIN_AGE_SECONDS
    ):
        return None
    return TemporaryFileCandidate(
        path=path.relative_to(root).as_posix(),
        device=str(info.st_dev),
        inode=str(info.st_ino),
        size=str(info.st_size),
        mtime_ns=str(info.st_mtime_ns),
    )


def _discover(root: Path) -> list[TemporaryFileCandidate]:
    candidates = []
    # Never classify TS/part/codec intermediates as disposable by extension.
    for pattern in ("**/*.tmp", "**/streamlink_*.log.*", "**/ffmpeg_*.log.*"):
        for path in sorted(root.glob(pattern)):
            if not _is_disposable_name(path):
                continue
            try:
                candidate = _snapshot(root, path)
            except OSError:
                continue
            if candidate is not None:
                candidates.append(candidate)
            if len(candidates) == MAX_CANDIDATES:
                return candidates
    return candidates


def _protected_directories(db: Session, root: Path) -> set[Path] | None:
    # Catalog association also protects completed-but-unprocessed/recoverable media.
    paths = set(db.scalars(select(Recording.path).where(Recording.path.isnot(None))))
    paths.update(
        db.scalars(
            select(Stream.recording_path).where(Stream.recording_path.isnot(None))
        )
    )
    protected = {
        Path(path).resolve(strict=False).parent for path in paths if path is not None
    }
    for lease in db.scalars(select(TwitchUpstreamLease)):
        state = (
            CaptureState.UNKNOWN
            if lease.state in {"STARTING", "ROTATING", "RECOVERING"}
            else physical_state(
                LocalCapture(
                    lease.process_pid,
                    lease.process_group_id,
                    lease.process_start_fingerprint,
                    False,
                )
            )
        )
        if state is CaptureState.DEAD or (
            lease.state == "RELEASED" and lease.process_pid is None
        ):
            continue
        username = db.scalar(
            select(Streamer.username).where(Streamer.twitch_id == lease.channel_key)
        )
        if username:
            protected.add(root / username)
        else:
            # An unresolvable reservation cannot authorize any destructive cleanup.
            return None
    return protected


def _open_parent(root: Path, relative: str) -> tuple[int, str]:
    parts = Path(relative).parts
    if (
        not parts
        or Path(relative).is_absolute()
        or any(part in {"..", "."} for part in parts)
    ):
        raise ValueError("Invalid temporary candidate path")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts[:-1]:
            following = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = following
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def _inspect(
    db: Session, root: Path, candidates: list[TemporaryFileCandidate], dry_run: bool
) -> dict[str, object]:
    protected = _protected_directories(db, root)
    if protected is None:
        return {
            "files_removed": 0,
            "space_freed_mb": 0,
            "errors": ["Capture reservation path is unverified"],
            "dry_run": dry_run,
            "candidates": [],
        }
    eligible = []
    errors = []
    removed = 0
    freed = 0
    for candidate in candidates:
        path = root / candidate.path
        if any(
            path.parent == directory
            or (directory != root and path.is_relative_to(directory))
            for directory in protected
        ):
            continue
        # Confirmation may select only the same genuine temporary filename class.
        if not _is_disposable_name(path):
            continue
        try:
            parent, name = _open_parent(root, candidate.path)
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                identity = tuple(
                    str(value)
                    for value in (
                        info.st_dev,
                        info.st_ino,
                        info.st_size,
                        info.st_mtime_ns,
                    )
                )
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or time.time() - info.st_mtime < MIN_AGE_SECONDS
                    or identity
                    != (
                        candidate.device,
                        candidate.inode,
                        candidate.size,
                        candidate.mtime_ns,
                    )
                ):
                    errors.append("Temporary candidate changed; preview again")
                    continue
                eligible.append(candidate.model_dump())
                if not dry_run:
                    os.unlink(name, dir_fd=parent)
                    removed += 1
                    freed += info.st_size
            finally:
                os.close(parent)
        except (OSError, ValueError):
            errors.append("Temporary candidate could not be safely removed")
    return {
        "files_removed": removed,
        "space_freed_mb": round(freed / (1024 * 1024), 2),
        "errors": errors,
        "dry_run": dry_run,
        "candidates": eligible,
    }


async def cleanup_temporary_files(
    root: Path, factory: sessionmaker[Session], request: TemporaryCleanupRequest
) -> dict[str, object]:
    if request.dry_run:

        def preview() -> dict[str, object]:
            with factory() as db:
                return _inspect(db, root, _discover(root), True)

        return await asyncio.to_thread(preview)
    # Admission and confirmed deletion share the existing persisted coordinator guard.
    coordinator = TwitchUpstreamCoordinator(
        session_factory=factory, monotonic_clock=time.monotonic
    )
    return await coordinator.run_capture_maintenance(
        lambda db: _inspect(db, root, request.candidates, False)
    )
