"""Actual signed TLS push uses closed owner catalogs and a draining worker."""

import asyncio
import json
from threading import Event, get_ident

import http_ece
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import event

from app.config.settings import Settings
from app.models import GlobalSettings, NotificationSettings, PushSubscription
from app.services.communication.enhanced_push_service import EnhancedPushService
from app.services.notifications import push_notification_service as module
from app.utils.async_db_utils import run_in_thread_pool
from tests.test_external_notification_boundary import notification_catalogs as _catalogs
from tests.test_webpush_delivery import b64, receiver as _tls_receiver

notification_catalogs = _catalogs
receiver = _tls_receiver


def owned_services(databases, receiver):
    services, public_keys = [], []
    for index, database in enumerate(databases):
        key = ec.generate_private_key(ec.SECP256R1())
        public_keys.append(key.public_key())
        settings = Settings(
            ENVIRONMENT="test",
            VAPID_PRIVATE_KEY=b64(
                key.private_numbers().private_value.to_bytes(32, "big")
            ),
            VAPID_PUBLIC_KEY=b64(
                key.public_key().public_bytes(
                    Encoding.X962, PublicFormat.UncompressedPoint
                )
            ),
            VAPID_CLAIMS_SUB="mailto:synthetic-owner@example.invalid",
            _env_file=None,
        )
        with database.sync_session_factory() as session:
            row = session.get(GlobalSettings, 1)
            for field in (
                "notify_online_global",
                "notify_offline_global",
                "notify_update_global",
                "notify_favorite_category_global",
            ):
                setattr(row, field, index == 0)
            session.add(
                PushSubscription(
                    id=1,
                    endpoint=receiver["subscription"]["endpoint"],
                    subscription_data=json.dumps(receiver["subscription"]),
                    is_active=True,
                )
            )
            session.commit()
        services.append(
            module.PushNotificationService(
                session_factory=database.sync_session_factory,
                push_service=EnhancedPushService(settings=settings),
            )
        )
    return services, public_keys


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_type, expected_type, expected_body, policy_field",
    [
        (
            "online",
            "stream_online",
            "Started streaming: literal stream\nCategory: Games",
            "notify_online",
        ),
        ("offline", "stream_offline", "Stream ended", "notify_offline"),
        (
            "update",
            "stream_update",
            "New title: literal stream\nCategory: Games",
            "notify_update",
        ),
        (
            "favorite_category",
            "favorite_category",
            "🎮 channel spielt jetzt Games!\n\nTitel: literal stream\nDieses Spiel ist in deinen Favoriten.",
            "notify_favorite_category",
        ),
    ],
)
async def test_push_event_isolation_closed_catalog_and_current_policy(
    notification_catalogs,
    receiver,
    monkeypatch,
    event_type,
    expected_type,
    expected_body,
    policy_field,
):
    databases = notification_catalogs
    services, public_keys = owned_services(databases, receiver)
    queries = []
    loop_thread = get_ident()
    for database in databases:
        event.listen(
            database.sync_engine,
            "before_cursor_execute",
            lambda *args: queries.append(get_ident()),
        )

    def forbidden_default():
        raise AssertionError("Push events must not borrow the legacy catalog")

    monkeypatch.setattr(module, "SessionLocal", forbidden_default)

    expected_owner = 0

    class CheckedRequests(list):
        def append(self, item):
            assert databases[expected_owner].sync_engine.pool.checkedout() == 0
            super().append(item)

    receiver["requests"] = CheckedRequests()
    assert await services[0].should_notify(1, event_type) is True
    assert await services[1].should_notify(1, event_type) is False
    assert await services[0].should_notify(1, "unknown") is False
    details = {
        "streamer_id": 1,
        "stream_id": 7,
        "title": "literal stream",
        "category_name": "Games",
    }
    await asyncio.gather(
        *(
            service.send_push_notifications("channel", event_type, details)
            for service in services
        )
    )
    assert len(receiver["requests"]) == 1
    _, headers, body = receiver["requests"][0]
    token = headers["Authorization"].split("t=", 1)[1].split(",")[0]
    origin = receiver["subscription"]["endpoint"].split("/push/")[0]
    assert (
        jwt.decode(token, public_keys[0], algorithms=["ES256"], audience=origin)["sub"]
        == "mailto:synthetic-owner@example.invalid"
    )
    payload = json.loads(
        http_ece.decrypt(
            body,
            private_key=receiver["ua"],
            auth_secret=receiver["auth"],
            version="aes128gcm",
        )
    )
    assert payload["body"] == expected_body
    assert payload["type"] == expected_type
    if event_type == "online":
        assert payload["data"]["stream_id"] == 7
    assert queries and loop_thread not in queries

    def switch_policy():
        for index, database in enumerate(databases):
            with database.sync_session_factory() as session:
                setattr(
                    session.get(GlobalSettings, 1), policy_field + "_global", index == 1
                )
                session.commit()

    await run_in_thread_pool(switch_policy)
    expected_owner = 1
    await asyncio.gather(
        *(
            service.send_push_notifications("channel", event_type, details)
            for service in services
        )
    )
    assert len(receiver["requests"]) == 2
    token = receiver["requests"][-1][1]["Authorization"].split("t=", 1)[1].split(",")[0]
    jwt.decode(token, public_keys[1], algorithms=["ES256"], audience=origin)
    with pytest.raises(jwt.exceptions.InvalidSignatureError):
        jwt.decode(token, public_keys[0], algorithms=["ES256"], audience=origin)

    def disable_channel():
        with databases[1].sync_session_factory() as session:
            session.add(NotificationSettings(streamer_id=1, **{policy_field: False}))
            session.commit()

    await run_in_thread_pool(disable_channel)
    assert await services[1].should_notify(1, event_type) is False
    await services[1].send_push_notifications("channel", event_type, details)
    assert len(receiver["requests"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [201, 410, 503])
async def test_push_delivery_keeps_worker_owned_through_cancellation(
    notification_catalogs, receiver, status
):
    databases = notification_catalogs
    services, _ = owned_services(databases, receiver)
    loop = asyncio.get_running_loop()
    entered, release = asyncio.Event(), Event()
    receiver["status"] = status

    class HeldRequests(list):
        def append(self, item):
            assert databases[0].sync_engine.pool.checkedout() == 0
            super().append(item)
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)

    receiver["requests"] = HeldRequests()
    task = asyncio.create_task(
        services[0].send_push_notifications("channel", "online", {"streamer_id": 1})
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 0.05)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert all(database.sync_engine.pool.checkedout() == 0 for database in databases)
    # Cancellation does not turn an unconsumed response into an expiry mutation.
    for database in databases:
        with database.sync_session_factory() as session:
            assert session.get(PushSubscription, 1).is_active is True


@pytest.mark.asyncio
@pytest.mark.parametrize("refreshed", [False, True])
async def test_push_expiry_updates_only_the_owning_unmodified_snapshot(
    notification_catalogs, receiver, refreshed
):
    databases = notification_catalogs
    services, _ = owned_services(databases, receiver)
    entered, release = asyncio.Event(), Event()
    loop = asyncio.get_running_loop()
    receiver["status"] = 410

    class HeldRequests(list):
        def append(self, item):
            assert databases[0].sync_engine.pool.checkedout() == 0
            super().append(item)
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)

    receiver["requests"] = HeldRequests()
    task = asyncio.create_task(
        services[0].send_push_notifications("channel", "online", {"streamer_id": 1})
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if refreshed:

            def refresh():
                with databases[0].sync_session_factory() as session:
                    row = session.get(PushSubscription, 1)
                    value = json.loads(row.subscription_data)
                    value["keys"]["auth"] = "replacement-synthetic-auth"
                    row.subscription_data = json.dumps(value)
                    session.commit()

            await run_in_thread_pool(refresh)
    finally:
        release.set()
        await task
    with databases[0].sync_session_factory() as session:
        assert session.get(PushSubscription, 1).is_active is refreshed
    with databases[1].sync_session_factory() as session:
        assert session.get(PushSubscription, 1).is_active is True


@pytest.mark.asyncio
async def test_first_parallel_push_initialization_does_not_drop_a_delivery(
    notification_catalogs, receiver, monkeypatch
):
    from app.services.communication import enhanced_push_service as enhanced_module

    services, _ = owned_services(notification_catalogs, receiver)
    service = services[0].push_service
    entered, release = asyncio.Event(), Event()
    loop = asyncio.get_running_loop()
    real_constructor = enhanced_module.ModernWebPushService

    def initialize(**kwargs):
        transport = real_constructor(**kwargs)
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        return transport

    monkeypatch.setattr(enhanced_module, "ModernWebPushService", initialize)
    first = asyncio.create_task(
        service.send_notification(receiver["subscription"], {"title": "first"})
    )
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(
            service.send_notification(receiver["subscription"], {"title": "second"})
        )
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), 0.05)
    finally:
        release.set()
        tasks = [first] + ([second] if second is not None else [])
        outcomes = await asyncio.gather(*tasks)
    assert outcomes == [True, True]
    payloads = [
        json.loads(
            http_ece.decrypt(
                item[2],
                private_key=receiver["ua"],
                auth_secret=receiver["auth"],
                version="aes128gcm",
            )
        )
        for item in receiver["requests"]
    ]
    assert sorted(payload["title"] for payload in payloads) == ["first", "second"]


@pytest.mark.asyncio
async def test_push_bootstrap_reset_then_json_subscription_and_invalid_inputs(
    notification_catalogs, receiver
):
    services, public_keys = owned_services(notification_catalogs, receiver)
    sender = EnhancedPushService(
        settings=Settings(
            ENVIRONMENT="test",
            VAPID_PRIVATE_KEY=None,
            VAPID_PUBLIC_KEY=None,
            _env_file=None,
        )
    )
    assert (
        await sender.send_notification(receiver["subscription"], {"title": "not ready"})
        is False
    )
    sender.settings = services[0].push_service.settings
    assert (
        await sender.send_notification(
            receiver["subscription"], {"title": "still not ready"}
        )
        is False
    )
    sender.reset_initialization()
    assert (
        await sender.send_notification(
            json.dumps(receiver["subscription"]), {"title": "reset ready"}
        )
        is True
    )
    origin = receiver["subscription"]["endpoint"].split("/push/")[0]
    token = receiver["requests"][0][1]["Authorization"].split("t=", 1)[1].split(",")[0]
    jwt.decode(token, public_keys[0], algorithms=["ES256"], audience=origin)
    for invalid in ("not-json", "[]", "null"):
        assert await sender.send_notification(invalid, {"title": "invalid"}) is False
    assert len(receiver["requests"]) == 1
