"""Execute native JSON/NFO/chapter/artwork preparation with independent catalogs."""

import builtins
from datetime import datetime, timedelta, timezone
import io
import json
import os
from functools import cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import subprocess
from threading import Thread, get_ident
import xml.etree.ElementTree as ET

import pytest
from sqlalchemy import event

from app.database import Base, DatabaseLifecycle
from app.bootstrap.application import create_app
from app.config.settings import Settings
from app.models import Stream, Streamer, StreamMetadata
from app.services.media.metadata_service import MetadataService
from app.services.system.logging_service import LoggingService
from app.utils.async_db_utils import run_in_thread_pool


@pytest.fixture
def image_origin():
    bodies, requests = {}, []

    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            body = bodies[self.path]
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", bodies, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("thumbnail_source", "composition"),
    [
        ("existing", "direct"),
        ("remote", "direct"),
        ("video", "direct"),
        ("video", "factory"),
        ("existing", "legacy-profile"),
    ],
)
async def test_real_metadata_pipeline_keeps_catalog_and_files_off_the_owner_loop(
    tmp_path, monkeypatch, image_origin, thumbnail_source, composition
):
    databases = []
    services = []
    directories = []
    loggers = []
    applications = []
    queries, files = [], []
    loop_thread = get_ident()
    native_open, native_io_open, native_stat = builtins.open, io.open, os.stat
    origin, bodies, requests = image_origin

    async def forbidden_default():
        raise AssertionError(
            "app metadata must not borrow the process-default image client"
        )

    from app.services.unified_image_service import unified_image_service

    monkeypatch.setattr(unified_image_service, "_get_session", forbidden_default)
    from app.services.media import metadata_service as metadata_module

    def forbidden_logging():
        raise AssertionError("app metadata must not borrow the process-default logger")

    monkeypatch.setattr(metadata_module, "get_logging_service", forbidden_logging)

    def observe(path):
        if isinstance(path, (str, os.PathLike)) and str(path).startswith(str(tmp_path)):
            files.append(get_ident())

    def opened(path, *args, **kwargs):
        observe(path)
        return native_open(path, *args, **kwargs)

    def io_opened(path, *args, **kwargs):
        observe(path)
        return native_io_open(path, *args, **kwargs)

    def stat(path, *args, **kwargs):
        observe(path)
        return native_stat(path, *args, **kwargs)

    try:
        for index in range(2):
            database = DatabaseLifecycle(f"sqlite:///{tmp_path / f'owner-{index}.db'}")
            databases.append(database)
            root = tmp_path / f"owner-{index}"
            (root / ".media").mkdir(parents=True)
            directory = root / "channel" / "Season 2026-11"
            directory.mkdir(parents=True)
            directories.append(directory)
            (directory / "capture.ts").write_bytes(b"original capture")
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc2=size=256x256:rate=1",
                    "-frames:v",
                    "1",
                    "-y",
                    str(directory / "capture-thumb.jpg"),
                ],
                check=True,
                capture_output=True,
                timeout=15,
            )
            assert (directory / "capture-thumb.jpg").stat().st_size > 1000
            bodies[f"/owner-{index}.jpg"] = (
                directory / "capture-thumb.jpg"
            ).read_bytes()
            if composition == "legacy-profile":
                (root / ".media" / "profiles").mkdir()
                (root / ".media" / "profiles" / "channel.jpg").write_bytes(
                    bodies[f"/owner-{index}.jpg"]
                )

            @cache
            def logging_factory(root=root):
                service = LoggingService(str(root / "logs"), isolated=True)
                loggers.append(service)
                return service

            if composition == "factory":
                application = create_app(
                    Settings(
                        ENVIRONMENT="test",
                        RECORDING_DIRECTORY=str(root),
                        LOGS_BASE_DIR=str(root / "logs"),
                        _env_file=None,
                    ),
                    database=database,
                )
                applications.append(application)
                service = application.state.background_queue_manager.task_handlers.metadata_service
            else:
                service = MetadataService(
                    session_factory=database.sync_session_factory,
                    logging_service_factory=logging_factory,
                    recordings_root_provider=lambda root=root: root,
                )
            services.append(service)
            if thumbnail_source != "existing":
                (directory / "capture-thumb.jpg").unlink()
            if thumbnail_source == "video":
                subprocess.run(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-loglevel",
                        "error",
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=256x256:rate=1",
                        "-t",
                        "12",
                        "-c:v",
                        "mpeg4",
                        "-y",
                        str(directory / "capture.mp4"),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=15,
                )
            with database.sync_engine.begin() as connection:
                connection.exec_driver_sql("BEGIN")
                Base.metadata.create_all(connection)
            with database.sync_session_factory() as session:
                session.add(
                    Streamer(
                        id=1,
                        username="channel",
                        twitch_id="channel",
                        profile_image_url="/data/images/profiles/channel.jpg"
                        if composition == "legacy-profile"
                        else f"{origin}/owner-{index}.jpg",
                    )
                )
                session.flush()
                started = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
                session.add(
                    Stream(
                        id=7,
                        streamer_id=1,
                        title=f"Owner {index}",
                        started_at=started,
                        ended_at=started + timedelta(minutes=5),
                        recording_path=str(directory / "capture.ts"),
                    )
                )
                session.flush()
                if thumbnail_source == "remote":
                    session.add(
                        StreamMetadata(
                            stream_id=7, thumbnail_url=f"{origin}/owner-{index}.jpg"
                        )
                    )
                session.commit()
            event.listen(
                database.sync_engine,
                "before_cursor_execute",
                lambda *_: queries.append(get_ident()),
            )

        with monkeypatch.context() as observed:
            observed.setattr(builtins, "open", opened)
            observed.setattr(io, "open", io_opened)
            observed.setattr(os, "stat", stat)
            for service, directory in zip(services, directories, strict=True):
                assert await service.generate_metadata_for_stream(
                    7, str(directory), "capture"
                )
        assert queries and loop_thread not in queries
        assert files and loop_thread not in files
        for index, (database, directory) in enumerate(
            zip(databases, directories, strict=True)
        ):
            metadata_json = json.loads((directory / "capture.info.json").read_text())
            assert f"Owner {index}" in json.dumps(metadata_json)
            episode = ET.parse(directory / "capture.nfo").getroot()
            assert episode.tag == "episodedetails"
            assert episode.findtext("title") == f"Owner {index}"
            assert (directory / "capture.vtt").read_text().startswith("WEBVTT")
            assert (directory / "capture.srt").is_file()
            assert (directory / "capture-ffmpeg-chapters.txt").is_file()
            assert (directory / "capture.xml").is_file()
            assert (directory / "capture.ts").read_bytes() == b"original capture"
            thumbnail = directory / "capture-thumb.jpg"
            assert thumbnail.stat().st_size > 1000
            assert (directory / "poster.jpg").read_bytes() == thumbnail.read_bytes()
            artwork = directory.parent.parent / ".media" / "artwork" / "channel"
            for name in ("poster.jpg", "logo.jpg", "fanart.jpg", "banner.jpg"):
                assert (artwork / name).read_bytes() == bodies[f"/owner-{index}.jpg"]
            with database.sync_session_factory() as session:
                stored = session.query(StreamMetadata).one()
                assert stored.stream_id == 7
                assert stored.json_path == str(directory / "capture.info.json")
                assert stored.nfo_path == str(directory / "capture.nfo")
                if thumbnail_source == "video":
                    assert stored.thumbnail_path == str(
                        directory / "capture_thumbnail.jpg"
                    )
            assert database.sync_engine.pool.checkedout() == 0
        expected = 10 if thumbnail_source == "remote" else 9
        if composition == "legacy-profile":
            expected = 0
        assert (
            requests.count("/owner-0.jpg") == requests.count("/owner-1.jpg") == expected
        )
    finally:
        for service in services:
            await service.close()
        for application in applications:
            await application.state.background_queue_manager.task_handlers.cleanup()
            await application.state.websocket_manager.close_all()
            if application.state.logging_service is not None:
                await run_in_thread_pool(application.state.logging_service.close)
        for database in databases:
            await database.adispose()
        for logger in loggers:
            await run_in_thread_pool(logger.close)
