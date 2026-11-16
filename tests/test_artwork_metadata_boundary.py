"""Legacy artwork entry points project identities before asynchronous work."""

import builtins
from datetime import datetime, timezone
import inspect
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from threading import get_ident
import xml.etree.ElementTree as ET

import pytest
from sqlalchemy import event
from PIL import Image

from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer
from app.services.media.artwork_service import ArtworkService


@pytest.mark.asyncio
@pytest.mark.parametrize("write_failure", [False, True])
async def test_artwork_metadata_gateway_reloads_only_its_owned_catalog_off_loop(
    tmp_path, monkeypatch, write_failure
):
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'artwork.db'}")
    root = tmp_path / "recordings"
    root.mkdir()
    service = ArtworkService(
        recordings_dir=root, session_factory=database.sync_session_factory
    )
    queries, writes = [], []
    loop_thread = get_ident()
    native_open = builtins.open

    def opened(path, *args, **kwargs):
        if str(path).startswith(str(root)):
            writes.append(get_ident())
            if write_failure and str(path).endswith("tvshow.nfo"):
                raise PermissionError("synthetic artwork metadata refusal")
        return native_open(path, *args, **kwargs)

    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            streamer = Streamer(
                id=1,
                username="alice",
                twitch_id="alice",
                created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
            )
            session.add(streamer)
            session.flush()
            session.add(
                Stream(
                    id=1,
                    streamer_id=1,
                    started_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
                )
            )
            session.commit()
        # The detached, expired row cannot safely lazy-load scalar attributes.
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_: queries.append(get_ident()),
        )
        operation = service.save_streamer_metadata(streamer)
        assert inspect.isawaitable(operation)
        if inspect.iscoroutine(operation):
            assert not any(
                isinstance(value, Streamer)
                for value in operation.cr_frame.f_locals.values()
            )
        with monkeypatch.context() as observed:
            observed.setattr(builtins, "open", opened)
            assert await operation is (not write_failure)
        assert queries and loop_thread not in queries
        assert writes and loop_thread not in writes
        if write_failure:
            assert await service.save_streamer_metadata(streamer)
        directory = root / ".media" / "metadata" / "alice"
        assert ET.parse(directory / "tvshow.nfo").getroot().findtext("title") == "alice"
        season = ET.parse(directory / "Season_2026-11" / "season.nfo").getroot()
        assert season.findtext("seasonnumber") == "202611"
        assert await service.save_streamer_artwork(streamer) is False  # no profile URL
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await service.close()
        await database.adispose()


@pytest.fixture
def image_origin():
    data = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(data, format="JPEG")
    content = data.getvalue()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/avatar.jpg", content, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["local", "http"])
async def test_standalone_artwork_owns_transport_and_file_io(
    tmp_path, monkeypatch, image_origin, source
):
    from app.services.unified_image_service import unified_image_service

    url, content, requests = image_origin
    root = tmp_path / "recordings"
    root.mkdir()
    local = root / "profile.jpg"
    local.write_bytes(content)
    service = ArtworkService(recordings_dir=root)
    writes = []
    loop_thread = get_ident()
    native_open = builtins.open

    def opened(path, *args, **kwargs):
        if str(path).startswith(str(root)):
            writes.append(get_ident())
        return native_open(path, *args, **kwargs)

    async def forbidden_global():
        raise AssertionError("borrowed process-default image transport")

    monkeypatch.setattr(unified_image_service, "_get_session", forbidden_global)
    try:
        for _ in range(2):
            with monkeypatch.context() as observed:
                observed.setattr(builtins, "open", opened)
                assert await service.save_artwork(
                    "alice", str(local) if source == "local" else url, None
                )
            directory = root / ".media" / "artwork" / "alice"
            images = list(directory.glob("*.jpg"))
            assert len(images) == 9
            assert all(path.read_bytes() == content for path in images)
            assert writes and loop_thread not in writes
            await service.close()
            for path in images:
                path.unlink()
        assert bool(requests) is (source == "http")
    finally:
        await service.close()
