"""Initialize per-channel settings inside the caller's transaction."""

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NotificationSettings, Streamer, StreamerRecordingSettings

_Settings = TypeVar("_Settings", NotificationSettings, StreamerRecordingSettings)


def initialize_channel_settings(
    db: Session, model: type[_Settings], streamer_id: int
) -> _Settings:
    """Resolve a missing lookup, without committing or overwriting a winner."""
    if db.get_bind(mapper=model).dialect.name == "postgresql":
        # Lock the existing parent, not the missing settings row. With READ
        # COMMITTED the new lookup sees settings committed by the lock holder.
        db.execute(
            select(Streamer.id)
            .where(Streamer.id == streamer_id)
            .with_for_update(key_share=True)
        ).scalar_one_or_none()
        row = db.query(model).filter_by(streamer_id=streamer_id).first()
        if row is not None:
            return row

    row = model(streamer_id=streamer_id)
    db.add(row)
    return row
