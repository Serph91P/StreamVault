"""A failed real channel-update query cannot publish an update or borrow a peer."""

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from app.config.settings import Settings
from app.services.communication.websocket_manager import ConnectionManager
from app.events.handler_registry import EventHandlerRegistry
from app.models import Streamer
from app.services.api.twitch_api import TwitchAPIService
from tests.test_external_notification_boundary import (
    notification_catalogs as notification_catalogs,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("database_error", [False, True])
async def test_update_query_failure_leaves_both_catalogues_unchanged(
    notification_catalogs, database_error, caplog
):
    first, peer = notification_catalogs
    settings = Settings(ENVIRONMENT="test", _env_file=None)
    client = TwitchAPIService(settings=settings)
    socket = ConnectionManager()

    def unavailable(*_args):
        if database_error:
            raise OperationalError("SELECT", {}, RuntimeError("synthetic query fault"))
        raise RuntimeError("synthetic query fault")

    registry = EventHandlerRegistry(
        socket,
        settings=settings,
        session_factory=first.sync_session_factory,
        twitch_api=client,
        recording_manager=object(),
        notification_service=object(),
    )
    before = []
    for database in (first, peer):
        with database.sync_session_factory() as session:
            before.append(
                list(
                    session.execute(
                        select(Streamer.id, Streamer.username, Streamer.title)
                    )
                )
            )
    event.listen(first.sync_engine, "before_cursor_execute", unavailable)
    try:
        await registry.handle_stream_update(
            {"broadcaster_user_id": "fixture", "title": "must not publish"}
        )
    finally:
        event.remove(first.sync_engine, "before_cursor_execute", unavailable)
        await client.close()
        await socket.close_all()
    assert (
        "Database error handling stream update"
        if database_error
        else "Error handling stream update"
    ) in caplog.text
    for index, database in enumerate((first, peer)):
        assert database.sync_engine.pool.checkedout() == 0
        with database.sync_session_factory() as session:
            assert (
                list(
                    session.execute(
                        select(Streamer.id, Streamer.username, Streamer.title)
                    )
                )
                == before[index]
            )
    assert not socket._event_log
