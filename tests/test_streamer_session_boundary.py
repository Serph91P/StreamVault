"""Streamer application methods return values from closed, owner-local DB workers."""

import asyncio
from dataclasses import is_dataclass
from threading import Event, get_ident
from types import SimpleNamespace

import pytest
from sqlalchemy import event, inspect

from app.services.streamer_service import StreamerService
from tests import test_image_http_ownership

image_applications = test_image_http_ownership.image_applications


def scoped_streamers(app, database):
    return StreamerService(
        session_factory=database.sync_session_factory,
        websocket_manager=app.state.websocket_manager,
        event_registry=SimpleNamespace(),
        twitch_api=SimpleNamespace(),
        image_service=SimpleNamespace(),
    )


@pytest.mark.asyncio
async def test_streamer_reads_are_owner_values_and_all_sql_is_off_loop(
    image_applications,
):
    applications, databases, _, queries = image_applications
    actors = [
        scoped_streamers(app, database)
        for app, database in zip(applications, databases)
    ]
    queries.clear()
    for index, actor in enumerate(actors):
        listed = await actor.get_streamers()
        assert len(listed) == 1
        assert listed[0].username == f"owner-{index}"
        assert inspect(listed[0], raiseerr=False) is None
        found = await actor.get_streamer_by_username(f"OWNER-{index}")
        assert found is not None and found.id == 1
        assert found.twitch_id == f"owner-{index}"
        assert found.profile_image_url == f"https://images.invalid/owner-{index}.jpg"
        assert inspect(found, raiseerr=False) is None
        assert is_dataclass(found) and found.__dataclass_params__.frozen
        assert await actor.get_streamer_by_username("missing") is None
        raw = await actor.get_all_streamers()
        assert len(raw) == 1 and raw[0] == found
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    assert queries and get_ident() not in [thread for thread, _ in queries]
    assert not hasattr(actors[0], "db"), (
        "application service must not retain a live Session"
    )


@pytest.mark.asyncio
async def test_streamer_worker_is_drained_before_repeated_cancellation_returns(
    image_applications,
):
    applications, databases, _, _ = image_applications
    actor = scoped_streamers(applications[0], databases[0])
    entered, release = Event(), Event()

    def hold(connection, cursor, sql, *args):
        if "FROM streamers" in sql and not entered.is_set():
            entered.set()
            assert release.wait(5), "test did not release its held SQL callback"

    event.listen(databases[0].sync_engine, "before_cursor_execute", hold)
    task = asyncio.create_task(actor.get_streamers())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert databases[0].sync_engine.pool.checkedout() == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        event.remove(databases[0].sync_engine, "before_cursor_execute", hold)


@pytest.mark.asyncio
async def test_streamer_add_refresh_delete_close_their_scopes_before_provider_awaits(
    image_applications,
):
    applications, databases, _, queries = image_applications
    notifications, subscriptions = [], []

    def pools_closed():
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )

    class API:
        async def get_users_by_login(self, logins):
            pools_closed()
            return [
                {
                    "id": "42",
                    "login": logins[0],
                    "display_name": "Added",
                    "profile_image_url": "https://images.invalid/first.jpg",
                    "description": "Original",
                }
            ]

        async def get_users_by_id(self, ids):
            pools_closed()
            return [
                {
                    "id": ids[0],
                    "login": "added",
                    "display_name": "Renamed",
                    "profile_image_url": "https://images.invalid/replaced.jpg",
                    "description": "Updated",
                }
            ]

        async def get_streams(self, *, user_ids):
            pools_closed()
            return []

    class Images:
        async def download_profile_image(self, identifier, url):
            pools_closed()
            return "/data/images/profiles/fixture.jpg"

        async def update_streamer_profile_image(self, identifier, url):
            pools_closed()
            return True

        def get_cached_profile_image(self, identifier):
            assert get_ident() != loop_thread
            return "/data/images/profiles/replaced.jpg"

        async def close(self):
            raise AssertionError("borrowed image owner must not be closed")

    class Registry:
        async def subscribe_to_events(self, twitch_id):
            pools_closed()
            subscriptions.append(("subscribe", twitch_id))

        async def unsubscribe_from_events(self, twitch_id):
            pools_closed()
            subscriptions.append(("unsubscribe", twitch_id))

    class Manager:
        async def send_notification(self, message):
            pools_closed()
            notifications.append(message)

    loop_thread = get_ident()
    actor = StreamerService(
        session_factory=databases[0].sync_session_factory,
        websocket_manager=Manager(),
        event_registry=Registry(),
        twitch_api=API(),
        image_service=Images(),
    )
    queries.clear()
    created = await actor.add_streamer("added")
    assert created is not None and created.twitch_id == "42"
    assert created.username == "Added" and created.description == "Original"
    assert inspect(created, raiseerr=False) is None
    assert is_dataclass(created) and created.__dataclass_params__.frozen
    existing = await actor.add_streamer("added")
    assert existing is not None and existing.id == created.id
    assert len(await actor.get_all_streamers()) == 2
    assert await actor.refresh_streamer_data(created.id) is True
    updated = await actor.get_streamer_by_username("Renamed")
    assert updated is not None and updated.id == created.id
    assert updated.description == "Updated"
    assert updated.profile_image_url == "/data/images/profiles/replaced.jpg"
    assert await actor.bulk_check_live_status([created.id]) == {created.id: False}
    assert await actor.refresh_streamer_data(999) is False
    assert await actor.delete_streamer(created.id) == {
        "twitch_id": "42",
        "username": "Renamed",
    }
    assert await actor.delete_streamer(created.id) is None
    assert [item.username for item in await actor.get_all_streamers()] == ["owner-0"]
    assert subscriptions == [("subscribe", "42"), ("unsubscribe", "42")]
    assert len(notifications) == 2
    assert queries and loop_thread not in [thread for thread, _ in queries]
    pools_closed()
    await actor.close()


@pytest.mark.asyncio
async def test_real_streamer_list_uses_the_factory_catalogue_without_request_session(
    image_applications,
):
    _, databases, clients, queries = image_applications
    queries.clear()
    for index, client in enumerate(clients):
        response = await client.get("/api/streamers")
        assert response.status_code == 200, response.text
        assert [item["username"] for item in response.json()["streamers"]] == [
            f"owner-{index}"
        ]
        assert all(
            database.sync_engine.pool.checkedout() == 0 for database in databases
        )
    reads = [thread for thread, sql in queries if "FROM streamers" in sql]
    assert reads and get_ident() not in reads
