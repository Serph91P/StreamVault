"""Immutable durable recording-state values, projected before session closure."""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from pydantic import JsonValue

from app.models import ActiveRecordingState


@dataclass(frozen=True, slots=True)
class ActiveRecordingSnapshot:
    id: int
    stream_id: int
    recording_id: int
    process_id: int
    process_identifier: str
    streamer_name: str
    started_at: datetime
    ts_output_path: str
    force_mode: bool | None
    quality: str | None
    status: str | None
    last_heartbeat: datetime
    config_json: str | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_row(cls, row: ActiveRecordingState) -> Self:
        return cls(
            id=row.id,
            stream_id=row.stream_id,
            recording_id=row.recording_id,
            process_id=row.process_id,
            process_identifier=row.process_identifier,
            streamer_name=row.streamer_name,
            started_at=row.started_at,
            ts_output_path=row.ts_output_path,
            force_mode=row.force_mode,
            quality=row.quality,
            status=row.status,
            last_heartbeat=row.last_heartbeat,
            config_json=row.config_json,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def get_config(self) -> JsonValue:
        # Parse on demand so callers never share mutable nested configuration.
        value: JsonValue = json.loads(self.config_json) if self.config_json else {}
        return value
