from datetime import datetime, timezone
import re
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)
from typing import Annotated, Optional, List, Dict, Self
from enum import Enum


class CleanupPolicyType(str, Enum):
    COUNT = "count"
    SIZE = "size"
    AGE = "age"
    CUSTOM = "custom"


MAX_RECORDING_COUNT = 2**31 - 1  # PostgreSQL Integer storage for legacy limits.
MAX_SIZE_GIB = (2**63 - 1) // 1024**3  # Signed 64-bit byte range.
MaxStreams = Annotated[int, Field(strict=True, ge=0, le=MAX_RECORDING_COUNT)]


def utc_datetime(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class PreserveTimeframeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    weekdays: Optional[List[Annotated[int, Field(strict=True, ge=0, le=6)]]] = None
    timeOfDay: Optional[Dict[str, str]] = None

    @field_validator("timeOfDay")
    @classmethod
    def validate_clock_range(
        cls, value: dict[str, str] | None
    ) -> dict[str, str] | None:
        if value is not None and (
            value.keys() != {"start", "end"}
            or any(
                not re.fullmatch(r"(?:[01]?[0-9]|2[0-3]):[0-5][0-9]", part)
                for part in value.values()
            )
        ):
            raise ValueError("timeOfDay requires valid start and end times (HH:MM)")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        try:
            start = (
                utc_datetime(datetime.fromisoformat(self.start_date))
                if self.start_date is not None
                else None
            )
            end = (
                utc_datetime(datetime.fromisoformat(self.end_date))
                if self.end_date is not None
                else None
            )
        except (ValueError, OverflowError) as error:
            raise ValueError(
                "preserve_timeframe dates must be valid ISO dates or datetimes"
            ) from error
        if start is not None and end is not None and start > end:
            raise ValueError("preserve_timeframe start_date must not be after end_date")
        return self


class CleanupPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: CleanupPolicyType
    threshold: int = Field(
        strict=True,
        ge=1,
        description="Positive integer: recordings, GiB or days, depending on type",
    )
    preserve_favorites: StrictBool = Field(
        default=True, description="Preserve recordings of favorite categories"
    )
    preserve_categories: Optional[List[str]] = Field(
        default=None, description="Categories to preserve"
    )
    preserve_timeframe: Optional[PreserveTimeframeSchema] = Field(
        default=None, description="Timeframe to preserve"
    )

    @model_validator(mode="after")
    def validate_threshold(self) -> Self:
        if self.type == CleanupPolicyType.CUSTOM:
            raise ValueError("cleanup policy type must be count, size or age")
        maximum = {
            CleanupPolicyType.COUNT: MAX_RECORDING_COUNT,
            CleanupPolicyType.SIZE: MAX_SIZE_GIB,
            CleanupPolicyType.AGE: datetime.now(timezone.utc).toordinal() - 1,
        }[self.type]
        if self.threshold > maximum:
            raise ValueError(
                f"{self.type.value} threshold must be between 1 and {maximum}"
            )
        return self


class RecordingSettingsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    enabled: bool = Field(default=True, description="Enable recording globally")
    output_directory: str = Field(
        default="/recordings", description="Directory to save recordings"
    )
    filename_template: str = Field(
        default="{streamer}/{streamer}_{year}-{month}-{day}_{hour}-{minute}_{title}_{game}",
        description="Template for recording filenames",
    )
    filename_preset: Optional[str] = Field(
        default="default", description="Preset template for recording filenames"
    )
    default_quality: str = Field(
        default="best", description="Default recording quality"
    )
    supported_codecs: str = Field(
        default="h264,h265",
        pattern=r"^(?:h264|h265|av1)(?:,(?:h264|h265|av1))*$",
        description="Global recording codec preferences (ordered h264, h265, av1 list)",
    )
    use_chapters: bool = Field(
        default=True, description="Create chapters based on stream events"
    )
    use_category_as_chapter_title: bool = Field(
        default=False,
        description="Use category name as chapter title instead of stream title",
    )
    max_streams_per_streamer: MaxStreams = Field(
        default=0,
        description="Maximum number of streams to keep per streamer (0 = unlimited)",
    )
    cleanup_policy: Optional[CleanupPolicySchema] = None


class StreamerRecordingSettingsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    streamer_id: int
    username: Optional[str] = None
    profile_image_url: Optional[str] = None
    enabled: bool = True
    quality: Optional[str] = None
    custom_filename: Optional[str] = None
    max_streams: Optional[MaxStreams] = None
    cleanup_policy: Optional[CleanupPolicySchema] = None
    use_global_cleanup_policy: bool = (
        True  # Use global cleanup policy or streamer-specific
    )
    supported_codecs: Optional[str] = (
        None  # Per-streamer codec preference (NULL = use global)
    )
    twitch_auth_priority: int = Field(
        default=0,
        ge=-1000,
        le=1000,
        description=(
            "Authenticated Twitch slot priority; higher values win. "
            "Equal priority keeps the current owner."
        ),
    )


class ActiveRecordingSchema(BaseModel):
    id: int
    stream_id: int
    streamer_id: int
    streamer_name: str
    title: str
    started_at: str
    file_path: str
    status: str
    duration: int
    twitch_auth_priority: int = 0
    effective_auth_mode: str = "unknown"
    pending_handoff: bool = False
    handoff_reason: Optional[str] = None
    partial_recording_warning: bool = False


class StorageUsageSchema(BaseModel):
    totalSize: int
    recordingCount: int
    oldestRecording: str
    newestRecording: str


class CleanupResultSchema(BaseModel):
    status: str
    message: str
    deleted_count: int
    deleted_paths: List[str]
