"""Kernel-held queue ownership on the same persistent media/SQLite filesystem.

A released lock is death evidence across Docker PID/hostname changes. A missing
marker or unsupported/unreadable lock is UNKNOWN, never an expiry-based takeover.
"""

from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
from uuid import UUID

try:
    import fcntl
except ImportError:  # Windows: normal work runs; crash takeover stays fail-closed.
    fcntl = None

queue_owner_fd: ContextVar[int | None] = ContextVar("queue_owner_fd", default=None)


class QueueOwnerFile:
    def __init__(self, directory: Path, token: str):
        self.directory = directory
        self.token = token
        self.fd = None

    def open(self):
        if self.fd is not None or fcntl is None:
            return
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(
            self.directory / self.token,
            os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd

    def close(self, *, remove=False):
        if self.fd is not None:
            # No LOCK_UN: an inherited child descriptor must retain the lock.
            os.close(self.fd)
            self.fd = None
            if remove:
                (self.directory / self.token).unlink(missing_ok=True)

    @contextmanager
    def dead_owner(self, token):
        fd = None
        dead = False
        try:
            try:
                valid = token and str(UUID(token)) == token
            except (ValueError, TypeError, AttributeError):
                valid = False
            if fcntl is not None and valid:
                try:
                    fd = os.open(self.directory / token, os.O_RDWR | os.O_NOFOLLOW)
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    dead = True
                except (OSError, ValueError):
                    dead = False
            yield dead
        finally:
            if fd is not None:
                os.close(fd)


queue_owner_file: ContextVar[QueueOwnerFile | None] = ContextVar(
    "queue_owner_file", default=None
)
