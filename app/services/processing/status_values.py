"""Typed JSON snapshot transported after processing-state transaction closure."""

from typing import Literal, TypedDict


class ProcessingSteps(TypedDict, total=False):
    metadata: str | None
    chapters: str | None
    mp4_remux: str | None
    mp4_validation: str | None
    thumbnail: str | None
    cleanup: str | None


class ProcessingStatusData(TypedDict):
    recording_id: int | None
    stream_id: int | None
    streamer_id: int | None
    statuses: ProcessingSteps
    last_error: str | None
    updated_at: str | None


class ProcessingStatus(TypedDict):
    type: Literal["recording_processing_status"]
    data: ProcessingStatusData


class RecordingAvailableData(TypedDict):
    stream_id: int
    streamer_id: int
    streamer_name: str
    recording_path: str
    title: str | None


class RecordingAvailable(TypedDict):
    type: Literal["recording_available"]
    data: RecordingAvailableData
