"""The thumbnail compatibility entry uses the same owned, bounded transport."""

from threading import get_ident

import pytest
from sqlalchemy import event

from app.database import Base, DatabaseLifecycle
from app.models import Stream, Streamer, StreamMetadata
from app.services.media.metadata_service import MetadataService

from tests.test_metadata_generation_ownership import image_origin as image_origin


@pytest.mark.asyncio
async def test_thumbnail_entry_persists_a_real_http_body_after_closing_its_session(
    tmp_path, monkeypatch, image_origin
):
    origin, bodies, requests = image_origin
    bodies["/thumbnail.jpg"] = b"synthetic image transport fixture"
    database = DatabaseLifecycle(f"sqlite:///{tmp_path / 'thumbnail.db'}")
    service = MetadataService(session_factory=database.sync_session_factory)
    queries = []
    loop_thread = get_ident()

    async def local_origin(username, width=1280, height=720):
        return origin + "/thumbnail.jpg"

    monkeypatch.setattr(service, "get_stream_thumbnail_url", local_origin)
    try:
        with database.sync_engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        with database.sync_session_factory() as session:
            session.add(Streamer(id=1, username="channel", twitch_id="channel"))
            session.flush()
            session.add(Stream(id=7, streamer_id=1))
            session.commit()
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *_: queries.append(get_ident()),
        )
        destination = tmp_path / "thumbnails"
        result = await service.download_twitch_thumbnail("channel", 7, str(destination))
        assert result == str(destination / "channel_thumbnail.jpg")
        assert (destination / "channel_thumbnail.jpg").read_bytes() == bodies[
            "/thumbnail.jpg"
        ]
        assert queries and loop_thread not in queries
        with database.sync_session_factory() as session:
            metadata = session.query(StreamMetadata).one()
            assert metadata.thumbnail_url == origin + "/thumbnail.jpg"
            assert metadata.thumbnail_path == result
        assert requests == ["/thumbnail.jpg"]
        assert database.sync_engine.pool.checkedout() == 0
    finally:
        await service.close()
        await database.adispose()


@pytest.mark.asyncio
async def test_owned_thumbnail_transport_is_recreated_after_a_queue_restart(
    tmp_path, image_origin
):
    origin, bodies, requests = image_origin
    bodies["/thumbnail.jpg"] = b"synthetic image transport fixture"
    service = MetadataService()
    try:
        assert await service._download_image(
            origin + "/thumbnail.jpg", tmp_path / "first.jpg"
        )
        await service.close()
        assert await service._download_image(
            origin + "/thumbnail.jpg", tmp_path / "after-restart.jpg"
        )
        assert (tmp_path / "after-restart.jpg").read_bytes() == bodies["/thumbnail.jpg"]
        assert requests == ["/thumbnail.jpg", "/thumbnail.jpg"]
    finally:
        await service.close()
