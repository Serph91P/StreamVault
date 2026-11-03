"""Domain events survive optional alert policy with real SQLite and replay."""

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import GlobalSettings, NotificationSettings, Streamer
from app.services.communication.websocket_manager import ConnectionManager
from app.services.notifications import external_notification_service as external_module
from app.services.notifications import push_notification_service as policy_module
from app.services.notifications.notification_dispatcher import NotificationDispatcher


EVENTS = [
    ("online", "stream.online", True),
    ("offline", "stream.offline", False),
    ("update", "channel.update", True),
]


@pytest.fixture
def policy_db(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'policy.sqlite'}")
    Base.metadata.create_all(
        engine,
        tables=[
            Streamer.__table__,
            GlobalSettings.__table__,
            NotificationSettings.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(Streamer(id=1, twitch_id="synthetic-1", username="synthetic"))
        db.add(
            GlobalSettings(
                id=1,
                notifications_enabled=True,
                notify_online_global=True,
                notify_offline_global=True,
                notify_update_global=True,
                notify_favorite_category_global=True,
            )
        )
        db.add(
            NotificationSettings(
                streamer_id=1,
                notify_online=True,
                notify_offline=True,
                notify_update=True,
                notify_favorite_category=True,
            )
        )
        db.commit()
    monkeypatch.setattr(policy_module, "SessionLocal", factory)
    monkeypatch.setattr(external_module, "SessionLocal", factory)
    yield factory
    engine.dispose()


async def dispatch(event_type, is_live, monkeypatch, failure=None):
    manager = ConnectionManager()
    dispatcher = NotificationDispatcher(manager)
    deliveries = []

    async def push(name, event, details):
        deliveries.append(("push", name, event, details["streamer_id"]))
        if failure == "push":
            raise RuntimeError("synthetic push transport failure")

    async def external(name, event, details):
        deliveries.append(("external", name, event, details["streamer_id"]))
        if failure == "external":
            raise RuntimeError("synthetic external transport failure")

    # Only external alert delivery is replaced; policy and replay stay real.
    monkeypatch.setattr(dispatcher.push_service, "send_push_notifications", push)
    monkeypatch.setattr(
        dispatcher.external_service, "send_stream_notification", external
    )
    await dispatcher.send_stream_notification(
        "synthetic",
        event_type,
        {
            "streamer_id": 1,
            "twitch_id": "synthetic-1",
            "title": "Updated title",
            "category_name": "Updated category",
            "is_live": is_live,
        },
    )
    return await manager.get_events_since(0), deliveries


def assert_domain_event(events, websocket_type, is_live):
    assert len(events) == 1
    event = events[0]
    assert event["type"] == websocket_type
    assert event["event_id"] == 1
    assert event["data"]["streamer_id"] == 1
    assert event["data"]["twitch_id"] == "synthetic-1"
    assert event["data"]["streamer_name"] == "synthetic"
    assert event["data"]["title"] == "Updated title"
    assert event["data"]["category_name"] == "Updated category"
    assert event["data"]["is_live"] is is_live


@pytest.mark.parametrize("event_type,websocket_type,is_live", EVENTS)
@pytest.mark.parametrize(
    "policy,alerts_allowed",
    [
        ("global-off", False),
        ("event-off", False),
        ("channel-off", False),
        ("missing-global", False),
        ("missing-channel", True),
        ("all-on", True),
    ],
)
def test_alert_policy_does_not_filter_domain_state(
    policy_db, monkeypatch, event_type, websocket_type, is_live, policy, alerts_allowed
):
    with policy_db() as db:
        global_settings = db.get(GlobalSettings, 1)
        channel_settings = db.query(NotificationSettings).one()
        if policy == "global-off":
            global_settings.notifications_enabled = False
        elif policy == "event-off":
            setattr(global_settings, f"notify_{event_type}_global", False)
        elif policy == "channel-off":
            setattr(channel_settings, f"notify_{event_type}", False)
        elif policy == "missing-global":
            db.delete(global_settings)
        elif policy == "missing-channel":
            db.delete(channel_settings)
        db.commit()

    events, deliveries = asyncio.run(dispatch(event_type, is_live, monkeypatch))
    assert_domain_event(events, websocket_type, is_live)
    assert deliveries == (
        [
            ("push", "synthetic", event_type, 1),
            ("external", "synthetic", event_type, 1),
        ]
        if alerts_allowed
        else []
    )


@pytest.mark.parametrize("event_type,websocket_type,is_live", EVENTS)
@pytest.mark.parametrize("failure", ["policy", "push", "external"])
def test_alert_failure_does_not_lose_or_duplicate_domain_state(
    policy_db, monkeypatch, event_type, websocket_type, is_live, failure
):
    if failure == "policy":

        def unavailable_policy():
            raise RuntimeError("synthetic policy database failure")

        monkeypatch.setattr(policy_module, "SessionLocal", unavailable_policy)

    events, deliveries = asyncio.run(
        dispatch(event_type, is_live, monkeypatch, failure)
    )
    assert_domain_event(events, websocket_type, is_live)
    if failure == "policy":
        assert deliveries == []


@pytest.mark.parametrize("enabled", [False, True])
def test_non_domain_alerts_keep_their_existing_policy(policy_db, monkeypatch, enabled):
    with policy_db() as db:
        db.get(GlobalSettings, 1).notifications_enabled = enabled
        db.commit()

    events, deliveries = asyncio.run(dispatch("favorite_category", True, monkeypatch))
    if enabled:
        assert_domain_event(events, "stream.favorite_category", True)
        assert len(deliveries) == 2
    else:
        assert events == []
        assert deliveries == []
