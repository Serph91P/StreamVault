"""Contracts for chapter category provenance and FFmpeg time ranges."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import StreamEvent, StreamMetadata
from app.routes.videos import get_video_chapters, parse_ffmpeg_chapters


class _Query:
    def __init__(self, value):
        self.value = value

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def first(self):
        return self.value

    def all(self):
        return self.value


class _ChapterDb:
    def __init__(self, stream, metadata, events):
        self.stream = stream
        self.metadata = metadata
        self.events = events
        self.event_queries = 0

    def query(self, model):
        if model is StreamMetadata:
            return _Query(self.metadata)
        if model is StreamEvent:
            self.event_queries += 1
            return _Query(self.events)
        return _Query(self.stream)


def _chapters(db):
    return asyncio.run(
        get_video_chapters(
            1,
            request=SimpleNamespace(),
            db=db,
            identity=SimpleNamespace(interactive=True),
        )
    )


def test_vtt_chapters_get_categories_from_matching_generated_event_provenance(tmp_path):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    vtt = tmp_path / "recording.vtt"
    vtt.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:10.250\nOpening (Games)\n\n"
        "00:00:10.250 --> 00:00:20.000\nMidstream (Music)\n",
        encoding="utf-8",
    )
    stream = SimpleNamespace(id=1, title="Recording", started_at=started_at, ended_at=started_at + timedelta(seconds=20))
    metadata = SimpleNamespace(chapters_vtt_path=str(vtt), chapters_ffmpeg_path=None)
    events = [
        SimpleNamespace(timestamp=started_at - timedelta(minutes=2), title="Opening", category_name="Games"),
        SimpleNamespace(timestamp=started_at, title="Ignored", category_name="Wrong"),
        SimpleNamespace(timestamp=started_at + timedelta(seconds=10.25), title="Midstream", category_name="Music"),
    ]
    db = _ChapterDb(stream, metadata, events)

    chapters = _chapters(db)

    assert [(chapter["title"], chapter["category_name"], chapter["start"], chapter["end"], chapter["end"] - chapter["start"]) for chapter in chapters] == [
        ("Opening (Games)", "Games", 0.0, 10.25, 10.25),
        ("Midstream (Music)", "Music", 10.25, 20.0, 9.75),
    ]
    assert db.event_queries == 1


def test_vtt_category_is_null_without_trusted_matching_provenance(tmp_path):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    vtt = tmp_path / "recording.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:04.000\nCustom title (not parsed)\n",
        encoding="utf-8",
    )
    stream = SimpleNamespace(id=1, title="Recording", started_at=started_at, ended_at=started_at + timedelta(seconds=4))
    metadata = SimpleNamespace(chapters_vtt_path=str(vtt), chapters_ffmpeg_path=None)
    db = _ChapterDb(
        stream,
        metadata,
        [SimpleNamespace(timestamp=started_at, title="Custom title", category_name="Wrong")],
    )

    chapters = _chapters(db)

    assert chapters == [{"id": 1, "start": 0.0, "end": 4.0, "title": "Custom title (not parsed)", "category_name": None}]


def test_vtt_provenance_handles_one_event_and_skips_duplicate_generated_offsets(tmp_path):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    vtt = tmp_path / "recording.vtt"
    vtt.write_text(
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\nOpening (Games)\n\n"
        "00:00:01.000 --> 00:00:04.000\nSwitch (Music)\n",
        encoding="utf-8",
    )
    stream = SimpleNamespace(id=1, title="Recording", started_at=started_at, ended_at=started_at + timedelta(seconds=4))
    metadata = SimpleNamespace(chapters_vtt_path=str(vtt), chapters_ffmpeg_path=None)
    db = _ChapterDb(
        stream,
        metadata,
        [
            SimpleNamespace(timestamp=started_at, title="Opening", category_name="Games"),
            SimpleNamespace(timestamp=started_at + timedelta(seconds=1), title="Switch", category_name="Music"),
            SimpleNamespace(timestamp=started_at + timedelta(seconds=1), title="Ignored", category_name="Wrong"),
        ],
    )

    chapters = _chapters(db)

    assert [chapter["category_name"] for chapter in chapters] == ["Games", "Music"]
    assert db.event_queries == 1


def test_vtt_without_event_history_keeps_category_null(tmp_path):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    vtt = tmp_path / "recording.vtt"
    vtt.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:04.000\nOpening\n", encoding="utf-8")
    stream = SimpleNamespace(id=1, title="Recording", started_at=started_at, ended_at=started_at + timedelta(seconds=4))
    metadata = SimpleNamespace(chapters_vtt_path=str(vtt), chapters_ffmpeg_path=None)
    db = _ChapterDb(stream, metadata, [])

    chapters = _chapters(db)

    assert chapters[0]["category_name"] is None
    assert db.event_queries == 1


def test_one_generated_event_provides_vtt_category_provenance(tmp_path):
    started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    vtt = tmp_path / "recording.vtt"
    vtt.write_text(
        "WEBVTT\n\n00:00:00.000 --> 00:00:04.000\nOpening (Games)\n",
        encoding="utf-8",
    )
    stream = SimpleNamespace(id=1, title="Recording", started_at=started_at, ended_at=started_at + timedelta(seconds=4))
    metadata = SimpleNamespace(chapters_vtt_path=str(vtt), chapters_ffmpeg_path=None)
    db = _ChapterDb(
        stream,
        metadata,
        [SimpleNamespace(timestamp=started_at, title="Opening", category_name="Games")],
    )

    chapters = _chapters(db)

    assert chapters[0]["category_name"] == "Games"
    assert db.event_queries == 1


def test_ffmpeg_chapters_respect_timebase_and_return_complete_valid_ranges():
    chapters = parse_ffmpeg_chapters(
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=125\nEND=10250\ntitle=Millis\n"
        "[CHAPTER]\nTIMEBASE=1/48000\nSTART=492000\nEND=960000\ntitle=Samples\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=5000\nEND=4000\ntitle=Invalid\n"
    )

    assert chapters == [
        {"id": 1, "start": 0.125, "end": 10.25, "title": "Millis"},
        {"id": 2, "start": 10.25, "end": 20.0, "title": "Samples"},
    ]
