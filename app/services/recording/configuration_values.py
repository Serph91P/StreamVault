"""Immutable recording configuration values; no sessions or ORM identities escape."""

from dataclasses import dataclass
from app.models import RecordingSettings, StreamerRecordingSettings


@dataclass(frozen=True)
class SegmentConfiguration:
    streamer_name: str | None
    proxy_enabled: bool
    fallback_to_direct: bool
    stored_proxy: str | None
    supported_codecs: str | None


@dataclass(frozen=True)
class RecordingConfiguration:
    id: int
    enabled: bool | None
    output_directory: str | None
    filename_template: str | None
    default_quality: str | None
    use_chapters: bool | None
    filename_preset: str | None
    use_category_as_chapter_title: bool | None
    max_streams_per_streamer: int | None
    cleanup_policy: str | None
    enable_proxy: bool | None
    proxy_health_check_enabled: bool | None
    proxy_health_check_interval_seconds: int | None
    proxy_max_consecutive_failures: int | None
    fallback_to_direct_connection: bool | None

    @classmethod
    def from_model(cls, row: RecordingSettings) -> "RecordingConfiguration":
        return cls(
            id=row.id,
            enabled=row.enabled,
            output_directory=row.output_directory,
            filename_template=row.filename_template,
            default_quality=row.default_quality,
            use_chapters=row.use_chapters,
            filename_preset=row.filename_preset,
            use_category_as_chapter_title=row.use_category_as_chapter_title,
            max_streams_per_streamer=row.max_streams_per_streamer,
            cleanup_policy=row.cleanup_policy,
            enable_proxy=row.enable_proxy,
            proxy_health_check_enabled=row.proxy_health_check_enabled,
            proxy_health_check_interval_seconds=row.proxy_health_check_interval_seconds,
            proxy_max_consecutive_failures=row.proxy_max_consecutive_failures,
            fallback_to_direct_connection=row.fallback_to_direct_connection,
        )


@dataclass(frozen=True)
class StreamerRecordingConfiguration:
    id: int
    streamer_id: int
    enabled: bool | None
    quality: str | None
    custom_filename: str | None
    max_streams: int | None
    cleanup_policy: str | None
    use_global_cleanup_policy: bool | None
    supported_codecs: str | None
    twitch_auth_priority: int

    @classmethod
    def from_model(
        cls, row: StreamerRecordingSettings
    ) -> "StreamerRecordingConfiguration":
        return cls(
            id=row.id,
            streamer_id=row.streamer_id,
            enabled=row.enabled,
            quality=row.quality,
            custom_filename=row.custom_filename,
            max_streams=row.max_streams,
            cleanup_policy=row.cleanup_policy,
            use_global_cleanup_policy=row.use_global_cleanup_policy,
            supported_codecs=row.supported_codecs,
            twitch_auth_priority=row.twitch_auth_priority,
        )
