"""Real owner-local logging files, redaction and permission-cache recovery."""

from pathlib import Path

import pytest

from app.services.system.logging_service import LoggingService


@pytest.mark.parametrize("level", ["debug", "error"])
def test_recording_and_media_log_methods_write_owned_context_and_redact(
    tmp_path, level
):
    root = tmp_path / "owner"
    peer = tmp_path / "peer"
    peer.mkdir()
    sentinel = peer / "keep.log"
    sentinel.write_text("peer bytes")
    service = LoggingService(str(root), isolated=True)
    try:
        service.recording_logger.setLevel("DEBUG")
        service.log_recording_activity(
            "fixture", "channel", "activity detail", level=level
        )
        service.log_recording_start(1, "channel", "720p", "capture.ts")
        service.log_recording_stop(1, "channel", 12.5, "capture.ts", "manual")
        service.log_recording_error(1, "channel", "transport", "bounded failure")
        service.log_stream_detection("channel", False)
        service.log_stream_detection(
            "channel", True, {"title": "Fixture title", "category_name": "Games"}
        )
        service.log_file_operation("remux", "capture.ts", True, "done", 12.5)
        service.log_file_operation("remux", "capture.ts", False)
        service.log_configuration_change("quality", "best", "720p")
        service.log_configuration_change("quality", "best", "720p", 1)
        service.log_recording_activity_to_file("fixture", "", "unknown owner fallback")
        service.log_post_processing_activity(
            "remux", "", "capture.ts", "capture.mp4", True, 2.5, "completed"
        )
        service.log_stream_event_to_file("online", "", "event detail")
        log_path = service.log_streamlink_start(
            "",
            "720p",
            "capture.ts",
            [
                "streamlink",
                "--twitch-api-header",
                "Authorization=OAuth synthetic-log-secret",
            ],
        )
        service.log_streamlink_output(
            "",
            b"synthetic-log-secret stdout",
            b"synthetic-log-secret stderr",
            0,
            log_path,
            known_secrets=("synthetic-log-secret",),
        )
        service.log_streamlink_error(
            "",
            b"synthetic-log-secret rejected",
            known_secrets=("synthetic-log-secret",),
        )
        assert Path(log_path).is_relative_to(root)
    finally:
        handlers = tuple(service._owned_handlers)
        service.close()
    text = "\n".join(path.read_text() for path in root.rglob("*.log"))
    for marker in (
        "RECORDING_START",
        "720p",
        "RECORDING_STOP",
        "12.50",
        "RECORDING_ERROR",
        "STREAM_DETECTION",
        "LIVE",
        "OFFLINE",
        "Fixture title",
        "FILE_OPERATION",
        "SUCCESS",
        "FAILED",
        "CONFIG_CHANGE",
        "Global",
        "Streamer 1",
        "activity detail",
        "unknown owner fallback",
        "capture.mp4",
        "2.50s",
        "event detail",
        "stdout",
        "stderr",
        "rejected",
    ):
        assert marker in text
    assert "synthetic-log-secret" not in text
    assert sentinel.read_text() == "peer bytes"
    assert all(handler.stream is None for handler in handlers)


def test_permission_cache_retries_failed_and_expired_checks_with_real_files(tmp_path):
    service = LoggingService(
        str(tmp_path / "logs"), isolated=True, test_permissions=True
    )
    blocked = tmp_path / "blocked"
    blocked.write_bytes(b"temporary owned obstruction")
    try:
        assert all(result for result, _ in service._permission_test_results.values())
        assert not list((tmp_path / "logs").rglob("test_write.tmp"))
        assert service._ensure_write_permission(blocked) is False
        assert service._force_permission_retest(blocked) is False
        blocked.unlink()
        blocked.mkdir()
        assert service._ensure_write_permission(blocked) is True
        assert service._ensure_write_permission(blocked) is True
        service._permission_test_results[str(blocked)] = (True, 0)
        assert service._ensure_write_permission(blocked) is True
        assert service._force_permission_retest(blocked) is True
        assert list(blocked.iterdir()) == []
        assert service.get_streamer_log_dir(blocked, "") == blocked
        obstruction = blocked / "channel"
        obstruction.write_bytes(b"keep obstruction")
        assert service.get_streamer_log_dir(blocked, "channel") == blocked
        assert obstruction.read_bytes() == b"keep obstruction"
    finally:
        service.close()


def test_invalid_log_root_fails_without_creating_handlers_or_changing_file(tmp_path):
    root = tmp_path / "not-a-directory"
    root.write_bytes(b"preserve root")
    with pytest.raises(OSError):
        LoggingService(str(root), isolated=True)
    assert root.read_bytes() == b"preserve root"
