"""Physical capture evidence shared by recovery and media maintenance.

Call database/proc inspection in the guarded worker thread, never on the loop.
Expiration and registry absence are not proof that a writer has exited.
"""

from app.utils.async_db_utils import run_in_thread_pool
import sqlite3
from dataclasses import dataclass
from enum import Enum

import psutil
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, object_session

from app.models import Recording, Stream, Streamer, TwitchUpstreamLease
from app.services.twitch_upstream_coordinator import ProcessInspector


class CaptureState(Enum):
    ALIVE = "alive"
    DEAD = "dead"
    UNKNOWN = "unknown"
    ABSENT = "absent"


@dataclass(frozen=True)
class LocalCapture:
    pid: int | None
    process_group_id: int | None
    fingerprint: str | None
    exited: bool


async def recording_is_protected(
    recording: Recording,
    snapshots: dict[str, LocalCapture],
) -> bool:
    """Use the caller's database, but never move its Session/ORM row to a worker."""
    source = object_session(recording)
    if source is None:
        return True
    if source.new or source.dirty or source.deleted:
        return True
    engine, recording_id = source.get_bind().engine, recording.id
    if engine.dialect.name == "sqlite":
        # Explicit test SQLite may share one connection; never roll back its caller.
        connection = source.connection().connection.driver_connection
        if isinstance(connection, sqlite3.Connection) and connection.in_transaction:
            return True

    def inspect() -> bool:
        with Session(bind=engine) as db:
            row = db.get(Recording, recording_id)
            if row is None:
                return True
            state = capture_state(db, row, snapshots.get(f"stream_{row.stream_id}"))
            return state in {CaptureState.ALIVE, CaptureState.UNKNOWN} or (
                state is CaptureState.ABSENT and row.status == "recording"
            )

    return await run_in_thread_pool(inspect)


def physical_state(identity: LocalCapture) -> CaptureState:
    if identity.exited:
        return CaptureState.DEAD
    if identity.pid is None:
        return CaptureState.UNKNOWN
    try:
        current = ProcessInspector().inspect(identity.pid)
    except psutil.NoSuchProcess:
        return CaptureState.DEAD
    except (psutil.Error, OSError):
        return CaptureState.UNKNOWN
    if (current.process_group_id, current.fingerprint) != (
        identity.process_group_id,
        identity.fingerprint,
    ):
        return CaptureState.UNKNOWN
    return CaptureState.ALIVE


def capture_state(
    db: Session,
    recording: Recording,
    local: LocalCapture | None,
) -> CaptureState:
    """Inspect under the coordinator admission guard and recording row lock."""
    channel_key = db.scalar(
        select(Streamer.twitch_id)
        .join(
            Stream,
            Stream.streamer_id == Streamer.id,
        )
        .where(Stream.id == recording.stream_id)
    )
    conditions = [TwitchUpstreamLease.recording_id == recording.id]
    if channel_key:
        conditions.append(TwitchUpstreamLease.channel_key == channel_key)
    leases = db.scalars(
        select(TwitchUpstreamLease).where(or_(*conditions)).with_for_update()
    ).all()
    states = [physical_state(local)] if local is not None else []
    for lease in leases:
        if lease.state in {"STARTING", "ROTATING", "RECOVERING"}:
            states.append(CaptureState.UNKNOWN)
        else:
            states.append(
                physical_state(
                    LocalCapture(
                        lease.process_pid,
                        lease.process_group_id,
                        lease.process_start_fingerprint,
                        False,
                    )
                )
            )
    if CaptureState.ALIVE in states:
        return CaptureState.ALIVE
    if CaptureState.UNKNOWN in states:
        return CaptureState.UNKNOWN
    return CaptureState.DEAD if states else CaptureState.ABSENT
