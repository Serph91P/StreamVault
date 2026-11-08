"""Worker-owned durable admission, claims and retry state for background work."""

import json
import os
import socket
from contextlib import ExitStack
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psutil
from sqlalchemy import select, func
from sqlalchemy.orm import aliased

from app.models.background_task import (
    BackgroundTask as StoredTask,
    BackgroundTaskDependency as Edge,
)
from app.services.queues.task_progress_tracker import (
    QueueTask,
    TaskPriority,
    TaskStatus,
)
from app.utils.security import sanitize_streamlink_output
from app.utils.queue_ownership import QueueOwnerFile

HEAVY_TASK_TYPES = frozenset(
    {
        "mp4_remux",
        "metadata_generation",
        "mp4_validation",
        "unified_recovery",
        "orphaned_recovery_check",
        "thumbnail_generation",
        "segment_concatenation",
        "metadata_embedding",
        "ts_to_mp4",
    }
)
TERMINAL = ("completed", "failed")


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    )


class DurableTaskStore:
    def __init__(self, session_factory):
        self.sessions = session_factory
        self.owner = str(uuid4())
        self.pid = os.getpid()
        self.started = psutil.Process(self.pid).create_time()
        self.host = socket.gethostname()
        self._owner_file = None

    def open_owner(self):
        if self._owner_file is None:
            with self.sessions() as db:
                url = db.get_bind().url
            if url.get_backend_name() == "sqlite" and url.database not in (
                None,
                "",
                ":memory:",
            ):
                root = Path(url.database).resolve().parent
            else:
                from app.config.settings import get_settings

                root = Path(get_settings().RECORDING_DIRECTORY).resolve()
            self._owner_file = QueueOwnerFile(
                root / ".streamvault-queue-owners", self.owner
            )
        self._owner_file.open()

    @property
    def owner_fd(self):
        return self._owner_file.fd if self._owner_file is not None else None

    @property
    def owner_file(self):
        return self._owner_file

    def close_owner(self, *, remove=False):
        if self._owner_file is not None:
            self._owner_file.close(remove=remove)
            self._owner_file = None
            self.owner = str(uuid4())

    @staticmethod
    def task(row):
        return QueueTask(
            id=row.id,
            task_type=row.task_type,
            priority=TaskPriority(row.priority),
            payload=row.payload,
            status=TaskStatus(row.status),
            created_at=utc(row.created_at),
            started_at=utc(row.started_at),
            progress=100.0 if row.status == "completed" else 0.0,
            completed_at=utc(row.completed_at),
            error_message=row.error_message,
            retry_count=row.retry_count,
            max_retries=row.max_retries,
        )

    @staticmethod
    def _lock_queue(db):
        # Admission, claims and retention must observe one dependency/status boundary.
        if db.get_bind().dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        elif db.get_bind().dialect.name == "postgresql":
            db.connection().exec_driver_sql(
                "SELECT pg_advisory_xact_lock(6005076117384319317)"
            )

    def accept(self, entries, recording_id=None):
        """One transaction accepts an entire dependency chain before acknowledging it."""
        for task, dependencies, streamer in entries:
            if len(json.dumps(task.payload).encode()) > 1024 * 1024:
                raise ValueError(
                    "Task payload exceeds the 1 MiB durable admission bound"
                )
        ids = {task.id for task, _, _ in entries}
        required = set().union(*(set(deps) for _, deps, _ in entries)) - ids
        with self.sessions() as db:
            state = None
            self._lock_queue(db)
            if recording_id is not None:
                from app.models import RecordingProcessingState

                state = (
                    db.query(RecordingProcessingState)
                    .filter_by(recording_id=recording_id)
                    .with_for_update()
                    .first()
                )
            found = set(
                db.scalars(select(StoredTask.id).where(StoredTask.id.in_(required)))
            )
            if found != required:
                raise ValueError("Unknown task dependency")
            existing = {
                row.id: row
                for row in db.scalars(
                    select(StoredTask)
                    .where(StoredTask.id.in_(ids))
                    .order_by(StoredTask.id)
                    .with_for_update()
                )
            }
            for task, _, streamer in entries:
                if task.id in existing:
                    if existing[task.id].task_type != task.task_type:
                        raise ValueError(
                            "Task identity already belongs to another handler"
                        )
                    if (
                        recording_id is not None
                        and existing[task.id].status in TERMINAL
                    ):
                        row = existing[task.id]
                        row.status, row.retry_count, row.error_message = (
                            "pending",
                            0,
                            None,
                        )
                        row.payload, row.ready_at = task.payload, task.created_at
                        row.started_at = row.completed_at = None
                    continue
                db.add(
                    StoredTask(
                        id=task.id,
                        task_type=task.task_type,
                        payload=task.payload,
                        streamer_key=streamer,
                        priority=task.priority.value,
                        status="pending",
                        created_at=task.created_at,
                        ready_at=task.created_at,
                        retry_count=0,
                        max_retries=task.max_retries,
                    )
                )
            db.flush()
            for task, dependencies, _ in entries:
                if task.id not in existing:
                    for dependency in dependencies:
                        if dependency == task.id:
                            raise ValueError("A task cannot depend on itself")
                        db.add(Edge(task_id=task.id, dependency_id=dependency))
            if state is not None:
                state.set_task_ids(
                    {
                        **state.get_task_ids(),
                        **{task.task_type: task.id for task, _, _ in entries},
                    }
                )
            db.commit()

    def recover(self, *, release_owned=False, after_id="", single_batch=False):
        """Only kernel-proven dead owners (or our drained stop) may be reset."""
        self.open_owner()
        cursor = after_id
        while True:
            with self.sessions() as db, ExitStack() as probes:
                if db.get_bind().dialect.name == "sqlite":
                    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
                rows = db.scalars(
                    select(StoredTask)
                    .where(StoredTask.status == "running", StoredTask.id > cursor)
                    .order_by(StoredTask.id)
                    .limit(100)
                    .with_for_update(skip_locked=True)
                ).all()
                if not rows:
                    return ""
                cursor = rows[-1].id
                dead_owners = {}
                for row in rows:
                    if row.owner_token not in dead_owners:
                        dead_owners[row.owner_token] = (
                            release_owned and row.owner_token == self.owner
                        ) or probes.enter_context(
                            self._owner_file.dead_owner(row.owner_token)
                        )
                    if dead_owners[row.owner_token]:
                        row.status = "pending"
                        row.owner_token = None
                db.commit()
                if single_batch:
                    return cursor if len(rows) == 100 else ""

    def claim(
        self,
        capacity,
        busy_streamers,
        heavy_capacity,
        isolated,
        *,
        global_capacity=None,
    ):
        self.open_owner()
        now = datetime.now(timezone.utc)
        parent = aliased(StoredTask)
        blocked = (
            select(1)
            .select_from(Edge)
            .join(parent, parent.id == Edge.dependency_id)
            .where(Edge.task_id == StoredTask.id, parent.status != "completed")
            .exists()
        )
        failed = (
            select(1)
            .select_from(Edge)
            .join(parent, parent.id == Edge.dependency_id)
            .where(Edge.task_id == StoredTask.id, parent.status == "failed")
            .exists()
        )
        claimed = []
        busy = set(busy_streamers)
        with self.sessions() as db:
            self._lock_queue(db)
            if global_capacity is not None:
                running = db.scalar(
                    select(func.count())
                    .select_from(StoredTask)
                    .where(StoredTask.status == "running")
                )
                capacity = min(capacity, max(0, global_capacity - running))
            running_heavy = db.scalar(
                select(func.count())
                .select_from(StoredTask)
                .where(
                    StoredTask.status == "running",
                    StoredTask.task_type.in_(HEAVY_TASK_TYPES),
                )
            )
            heavy_capacity = min(heavy_capacity, max(0, 2 - running_heavy))
            for row in db.scalars(
                select(StoredTask)
                .where(StoredTask.status.in_(("pending", "retrying")), failed)
                .limit(100)
            ):
                row.status = "failed"
                row.completed_at = now
                row.error_message = "Dependency failed"
            db.flush()
            # Reserve light execution capacity instead of parking every worker on a media semaphore.
            for heavy, slots in (
                (True, min(heavy_capacity, capacity)),
                (False, capacity),
            ):
                for _ in range(slots):
                    if len(claimed) >= capacity:
                        break
                    query = select(StoredTask).where(
                        StoredTask.status.in_(("pending", "retrying")),
                        StoredTask.ready_at <= now,
                        ~blocked,
                    )
                    query = query.where(
                        StoredTask.task_type.in_(HEAVY_TASK_TYPES)
                        if heavy
                        else StoredTask.task_type.not_in(HEAVY_TASK_TYPES)
                    )
                    if isolated and busy:
                        query = query.where(StoredTask.streamer_key.not_in(busy))
                    if isolated:
                        active = aliased(StoredTask)
                        query = query.where(
                            StoredTask.streamer_key.not_in(
                                select(active.streamer_key).where(
                                    active.status == "running"
                                )
                            )
                        )
                    row = db.scalars(
                        query.order_by(
                            StoredTask.priority.desc(),
                            StoredTask.created_at,
                            StoredTask.id,
                        )
                        .limit(1)
                        .with_for_update(skip_locked=True)
                    ).first()
                    if row is None:
                        break
                    row.status = "running"
                    row.started_at = now
                    (
                        row.owner_token,
                        row.owner_pid,
                        row.owner_started,
                        row.owner_host,
                    ) = self.owner, self.pid, self.started, self.host
                    db.flush()
                    claimed.append((self.task(row), row.streamer_key))
                    busy.add(row.streamer_key)
            db.commit()
        return claimed

    def finish(self, task_id, *, success, error=None, interrupted=False):
        with self.sessions() as db:
            row = db.get(StoredTask, task_id, with_for_update=True)
            if row is None or row.owner_token != self.owner or row.status != "running":
                if interrupted:
                    return self.task(row) if row is not None else None
                raise RuntimeError("Durable task ownership changed")
            now = datetime.now(timezone.utc)
            if interrupted:
                row.status = "pending"
            elif success:
                row.status = "completed"
                row.completed_at = now
            elif row.retry_count < row.max_retries:
                row.retry_count += 1
                row.status = "retrying"
                row.ready_at = now + timedelta(seconds=min(2**row.retry_count, 60))
            else:
                row.status = "failed"
                row.completed_at = now
            row.error_message = (
                sanitize_streamlink_output(str(error))[:4096] if error else None
            )
            row.owner_token = None
            result = self.task(row)
            db.commit()
            return result

    def step_completed(self, task):
        from app.models import RecordingProcessingState

        fields = {
            "metadata_generation": "metadata_status",
            "chapters_generation": "chapters_status",
            "mp4_remux": "mp4_remux_status",
            "mp4_validation": "mp4_validation_status",
            "thumbnail_generation": "thumbnail_status",
            "cleanup": "cleanup_status",
        }
        field = fields.get(task.task_type)
        recording_id = task.payload.get("recording_id")
        if not field or not recording_id:
            return False
        with self.sessions() as db:
            state = (
                db.query(RecordingProcessingState)
                .filter_by(recording_id=recording_id)
                .first()
            )
            return state is not None and getattr(state, field) == "completed"

    def snapshot(self, ids):
        with self.sessions() as db:
            return {
                row.id: self.task(row)
                for row in db.scalars(select(StoredTask).where(StoredTask.id.in_(ids)))
            }

    def recent(self):
        with self.sessions() as db:
            rows = db.scalars(
                select(StoredTask)
                .where(StoredTask.status.in_(TERMINAL))
                .order_by(StoredTask.completed_at.desc(), StoredTask.id)
                .limit(1000)
            ).all()
            return {row.id: self.task(row) for row in reversed(rows)}

    def counts(self):
        from sqlalchemy import func

        with self.sessions() as db:
            return dict(
                db.execute(
                    select(StoredTask.status, func.count()).group_by(StoredTask.status)
                ).all()
            )

    def prune(self, keep=1000):
        parent = aliased(StoredTask)
        protected = (
            select(1)
            .select_from(Edge)
            .join(parent, parent.id == Edge.task_id)
            .where(Edge.dependency_id == StoredTask.id, parent.status.not_in(TERMINAL))
            .exists()
        )
        with self.sessions() as db:
            self._lock_queue(db)
            ids = list(
                db.scalars(
                    select(StoredTask.id)
                    .where(StoredTask.status.in_(TERMINAL), ~protected)
                    .order_by(StoredTask.completed_at.desc())
                    .offset(keep)
                    .limit(100)
                )
            )
            if ids:
                db.query(Edge).filter(
                    Edge.task_id.in_(ids) | Edge.dependency_id.in_(ids)
                ).delete(synchronize_session=False)
                db.query(StoredTask).filter(StoredTask.id.in_(ids)).delete(
                    synchronize_session=False
                )
                db.commit()
        return len(ids)
