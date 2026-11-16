"""Real offline media and filesystem outcomes of the retained FFmpeg utilities."""

import json
from pathlib import Path
import subprocess

import pytest

from app.utils import ffmpeg_utils as media
from app.services.system.logging_service import LoggingService


@pytest.fixture
def transport_stream(tmp_path):
    path = tmp_path / "source.ts"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=10",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "1",
            "-threads",
            "1",
            "-c:v",
            "mpeg2video",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ]
        )
    )


@pytest.mark.asyncio
async def test_native_remux_metadata_and_duration_have_real_media_effects(
    transport_stream,
):
    source = transport_stream
    target = source.with_suffix(".mp4")
    chapter_path = source.with_name("chapters.txt")
    assert await media.create_ffmpeg_chapters_file(
        [{"start_time": 0, "end_time": 1, "title": "Opening"}],
        str(chapter_path),
        title="Owned recording",
        artist="Local fixture",
        date="2026-01-01",
    )
    logs = LoggingService(str(source.parent / "logs"), isolated=True)
    try:
        result = await media.convert_ts_to_mp4(
            str(source),
            str(target),
            str(chapter_path),
            logging_service=logs,
            streamer_name="offline-fixture",
        )
    finally:
        logs.close()
    written_logs = list((source.parent / "logs" / "ffmpeg").rglob("*.log"))
    assert written_logs
    log_text = "\n".join(path.read_text() for path in written_logs)
    assert "ts_to_mp4" in log_text and "offline-fixture" in log_text
    assert result["success"] and result["code"] == 0
    actual = probe(target)
    assert {stream["codec_type"] for stream in actual["streams"]} >= {"audio", "video"}
    assert actual["format"]["tags"]["title"] == "Owned recording"
    assert actual["format"]["tags"]["artist"] == "Local fixture"
    assert await media.validate_mp4(str(target))
    duration = await media.extract_video_duration(str(target))
    assert duration is not None and 0.9 <= duration <= 1.5
    before = target.read_bytes()
    rejected = await media.convert_ts_to_mp4(str(source), str(target))
    assert rejected == {
        "success": False,
        "code": -1,
        "stderr": "Output file already exists",
    }
    assert target.read_bytes() == before
    assert (await media.convert_ts_to_mp4(str(source), str(target), overwrite=True))[
        "success"
    ]
    tagged = source.with_name("tagged.mp4")
    assert await media.embed_metadata_in_mp4(
        str(target), str(tagged), {"title": "Tagged", "comment": ""}
    )
    assert probe(tagged)["format"]["tags"]["title"] == "Tagged"
    assert source.exists()


@pytest.mark.asyncio
async def test_native_metadata_wrapper_writes_owned_logs_for_success_and_failure(
    transport_stream, monkeypatch
):
    source = transport_stream
    monkeypatch.setattr(media.tempfile, "tempdir", str(source.parent))
    target = source.with_suffix(".mp4")
    logs = LoggingService(str(source.parent / "wrapper-logs"), isolated=True)
    try:
        result = await media.embed_metadata_with_ffmpeg_wrapper(
            str(source),
            str(target),
            {
                "title": "Wrapper fixture",
                "artist": "Offline",
                "date": "2026-01-01",
                "creation_time": "2026-01-01",
            },
            chapters=[{"start_time": 0, "end_time": 1, "title": "Opening"}],
            streamer_name="offline-wrapper",
            logging_service=logs,
        )
        assert result["success"] and target.exists()
        assert probe(target)["format"]["tags"]["title"] == "Wrapper fixture"
        corrupt = source.with_name("corrupt.ts")
        corrupt.write_bytes(b"corrupt fixture")
        rejected = await media.embed_metadata_with_ffmpeg_wrapper(
            str(corrupt),
            str(source.with_name("failed.mp4")),
            {"title": "Failed"},
            streamer_name="offline-wrapper",
            logging_service=logs,
        )
        assert not rejected["success"] and rejected["code"] != 0
    finally:
        logs.close()
    text = "\n".join(
        path.read_text() for path in (source.parent / "wrapper-logs").rglob("*.log")
    )
    assert "FFMPEG_METADATA_START" in text and "FFMPEG_METADATA_SUCCESS" in text
    assert "offline-wrapper" in text
    assert not list(source.parent.glob("*.txt"))


@pytest.mark.asyncio
async def test_missing_corrupt_and_tiny_media_report_failure_not_success(tmp_path):
    missing = tmp_path / "missing.ts"
    target = tmp_path / "out.mp4"
    assert await media.convert_ts_to_mp4(str(missing), str(target)) == {
        "success": False,
        "code": -1,
        "stderr": "Input file does not exist",
    }
    assert not await media.validate_mp4(str(missing))
    assert await media.extract_video_duration(str(missing)) is None
    corrupt = tmp_path / "corrupt.ts"
    corrupt.write_bytes(b"not a transport stream")
    assert not await media.validate_mp4(str(corrupt))
    result = await media.convert_ts_to_mp4(str(corrupt), str(target))
    assert not result["success"] and result["code"] != 0 and result["stderr"]
    assert not await media.embed_metadata_in_mp4(
        str(corrupt), str(target), {"title": "No"}
    )
    assert not target.exists()


@pytest.mark.asyncio
async def test_metadata_text_and_chapter_overwrite_contracts(tmp_path, monkeypatch):
    monkeypatch.setattr(media.tempfile, "tempdir", str(tmp_path))
    result = await media.create_metadata_file(
        {"title": "plain", "empty": "", "zero": 0}
    )
    assert result is not None
    metadata = Path(result)
    try:
        assert metadata.parent == tmp_path
        assert metadata.read_text() == ";FFMETADATA1\ntitle=plain\n"
    finally:
        metadata.unlink()
    target = tmp_path / "nested" / "chapters.txt"
    chapter = {"start_time": "0.125", "end_time": 1.25, "title": "a=b"}
    assert await media.create_ffmpeg_chapters_file([chapter], str(target))
    assert target.read_text() == (
        ";FFMETADATA1\n\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=125\nEND=1250\ntitle=a\\=b\n"
    )
    before = target.read_bytes()
    assert not await media.create_ffmpeg_chapters_file([], str(target))
    assert target.read_bytes() == before
    assert await media.create_ffmpeg_chapters_file(
        [], str(target), date="2026", overwrite=True
    )
    assert (
        target.read_text() == ";FFMETADATA1\ndate=2026\nyear=2026\ncreation_time=2026\n"
    )
    blocked = tmp_path / "not-a-directory"
    blocked.write_bytes(b"preserve")
    assert not await media.create_ffmpeg_chapters_file([], str(blocked / "child.txt"))
    assert blocked.read_bytes() == b"preserve"


@pytest.mark.asyncio
async def test_unavailable_executables_return_failure_without_touching_inputs(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.ts"
    source.write_bytes(b"synthetic source" * 1000)
    target = tmp_path / "target.mp4"
    # Real process creation fails at the OS executable lookup, not a fake child response.
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    assert await media.extract_video_duration(str(source)) is None
    assert not await media.embed_metadata_in_mp4(
        str(source), str(target), {"title": "test"}
    )
    result = await media.convert_ts_to_mp4(str(source), str(target))
    assert result["success"] is False and result["code"] != 0
    assert not target.exists() and source.read_bytes() == b"synthetic source" * 1000


@pytest.mark.asyncio
async def test_metadata_tempfile_and_validation_stat_failures_are_bounded(
    tmp_path, monkeypatch
):
    blocked = tmp_path / "not-a-directory"
    blocked.write_bytes(b"keep")
    monkeypatch.setattr(media.tempfile, "tempdir", str(blocked))
    assert await media.create_metadata_file({"title": "test"}) is None
    assert not await media.validate_mp4("\0invalid-path")
    assert blocked.read_bytes() == b"keep"
