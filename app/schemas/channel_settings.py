"""Shared partial wire contract for per-channel recording and notifications."""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, StrictBool, StrictStr, model_validator

from app.schemas.recording import MaxStreams

Quality = Literal[
    "",
    "best",
    "worst",
    "source",
    "1440p60",
    "1080p60",
    "1080p",
    "720p60",
    "720p",
    "480p",
    "360p",
    "160p",
    "audio_only",
]
Codecs = Annotated[
    StrictStr,
    Field(
        pattern=r"^(?:[ \t]*(?:h264|h265|av1)(?:[ \t]*,[ \t]*(?:h264|h265|av1))*[ \t]*)?$"
    ),
]


class ChannelRecordingPatch(BaseModel):
    enabled: StrictBool = True
    quality: Quality | None = None
    custom_filename: StrictStr | None = None
    supported_codecs: Codecs | None = None
    use_global_cleanup_policy: StrictBool = True
    max_streams: MaxStreams | None = None


class ChannelNotificationsPatch(BaseModel):
    notify_online: StrictBool = True
    notify_offline: StrictBool = True
    notify_update: StrictBool = True
    notify_favorite_category: StrictBool = False


class ChannelSettingsPatch(BaseModel):
    """Only supplied fields change. Flags must be JSON booleans; blocks must
    be objects. Null/empty text clears quality, filename and codec overrides;
    null clears maxStreams. Cleanup inheritance is an explicit boolean and
    doesn't erase the stored policy. Legacy aliases can accompany nested
    values if they agree after normalization. Unknown fields are ignored for
    compatibility; they are never written.
    """

    recording: ChannelRecordingPatch = Field(default_factory=ChannelRecordingPatch)
    notifications: ChannelNotificationsPatch = Field(
        default_factory=ChannelNotificationsPatch
    )
    autoRecord: StrictBool = True
    quality: Quality | None = None
    filenameTemplate: StrictStr | None = None
    supportedCodecs: Codecs | None = None
    useGlobalCleanupPolicy: StrictBool = True
    maxStreams: MaxStreams | None = None

    def recording_updates(self) -> dict[str, Any]:
        """Return only explicitly supplied recording updates, using storage names."""

        def normalize(key: str, value: Any) -> Any:
            if (
                key in {"quality", "custom_filename", "supported_codecs"}
                and value == ""
            ):
                return None
            if key == "supported_codecs" and value is not None:
                return ",".join(codec.strip() for codec in value.split(","))
            return value

        updates = {
            key: normalize(key, value)
            for key, value in self.recording.model_dump(exclude_unset=True).items()
        }
        for alias, key in (
            ("autoRecord", "enabled"),
            ("quality", "quality"),
            ("filenameTemplate", "custom_filename"),
            ("supportedCodecs", "supported_codecs"),
            ("useGlobalCleanupPolicy", "use_global_cleanup_policy"),
            ("maxStreams", "max_streams"),
        ):
            if alias not in self.model_fields_set:
                continue
            value = normalize(key, getattr(self, alias))
            if key in updates and updates[key] != value:
                raise ValueError(f"Conflicting values for recording.{key} and {alias}")
            updates[key] = value
        return updates

    @model_validator(mode="after")
    def validate_aliases(self) -> Self:
        self.recording_updates()
        return self
