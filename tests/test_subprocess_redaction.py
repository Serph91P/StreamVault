from app.services.system.logging_service import LoggingService
from app.utils.security import (
    StreamingStreamlinkOutputSanitizer,
    sanitize_command_for_logging,
    sanitize_streamlink_output,
)


def test_ffmpeg_argv_redacts_split_headers_and_url_credentials():
    command = [
        "ffmpeg",
        "-headers",
        "Authorization: Bearer split-secret\r\nCookie: session=secret-cookie",
        "-i",
        "https://user:secret-password@example.test/video?token=query-secret",
        "output.ts",
    ]

    sanitized = sanitize_command_for_logging(command)

    for secret in (
        "split-secret",
        "secret-cookie",
        "secret-password",
        "query-secret",
    ):
        assert secret not in sanitized
    assert "output.ts" in sanitized


def test_child_output_redacts_known_secret_split_across_chunks():
    sanitizer = StreamingStreamlinkOutputSanitizer(("fragmented-secret",))

    output = sanitizer.feed(b"failure token=fragmented-")
    output += sanitizer.feed(b"secret\n")
    output += sanitizer.flush()

    assert "fragmented-secret" not in output
    assert "[REDACTED]" in output


def test_failure_diagnostic_redacts_ffmpeg_headers_and_query_values():
    diagnostic = (
        "ffmpeg failed: Authorization: Bearer header-secret "
        "https://example.test/input?sig=query-secret"
    )

    sanitized = sanitize_streamlink_output(diagnostic)

    assert "header-secret" not in sanitized
    assert "query-secret" not in sanitized


def test_ffmpeg_child_output_is_redacted_before_file_persistence(tmp_path):
    log_path = tmp_path / "ffmpeg.log"
    service = object.__new__(LoggingService)
    service.get_ffmpeg_log_path = lambda operation, streamer_name: str(log_path)
    service._force_permission_retest = lambda log_dir: True

    service.log_ffmpeg_output(
        "probe",
        b"input token=stdout-secret",
        b"Authorization: Bearer stderr-secret",
        1,
        "synthetic",
        known_secrets=("stdout-secret", "stderr-secret"),
    )

    persisted = log_path.read_text()
    assert "stdout-secret" not in persisted
    assert "stderr-secret" not in persisted
    assert "[REDACTED]" in persisted
