"""The registered channel settings route validates a partial write before touching rows."""

import pytest
from sqlalchemy import select

from app.dependencies import get_application_event_registry
from app.models import (
    GlobalSettings,
    NotificationSettings,
    Streamer,
    StreamerRecordingSettings,
)
from tests.test_recording_capabilities import headers, stack  # noqa: F401

PATH = "/api/streamers/streamer/1"
FLAGS = [
    ("recording", "enabled"),
    ("recording", "use_global_cleanup_policy"),
    ("notifications", "notify_online"),
    ("notifications", "notify_offline"),
    ("notifications", "notify_update"),
    ("notifications", "notify_favorite_category"),
]


@pytest.fixture(params=[False, True], ids=["first-save", "existing"])
def channel(stack, request):  # noqa: F811
    app, database, _, client, _ = stack
    # GET mounts the provider registry even though channel readback does not use it.
    app.dependency_overrides[get_application_event_registry] = lambda: None
    with database.sync_session_factory() as db:
        if request.param:
            db.add(NotificationSettings(streamer_id=1))
        else:
            db.delete(db.scalar(select(StreamerRecordingSettings)))
        db.add(Streamer(id=2, username="unrelated", twitch_id="2"))
        db.flush()
        db.add_all(
            [
                StreamerRecordingSettings(streamer_id=2, quality="480p"),
                NotificationSettings(streamer_id=2, notify_online=False),
            ]
        )
        db.commit()
    return client, database, headers(stack, "jwt-cookie", "admin")


def snapshot(database, *, unrelated=False):
    with database.sync_session_factory() as db:
        result = []
        for model in (GlobalSettings, StreamerRecordingSettings, NotificationSettings):
            table = model.__table__
            query = select(table).order_by(table.c.id)
            if unrelated and model is not GlobalSettings:
                query = query.where(table.c.streamer_id == 2)
            result.append(db.execute(query).all())
        return result


def put(channel, payload):
    client, _, auth = channel
    return client.put(f"{PATH}/settings", json=payload, headers=auth)


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("value", ["false", "true", 0, 1, [], {}, None])
def test_flag_must_be_json_boolean(channel, flag, value):
    _, database, _ = channel
    before = snapshot(database)
    block, key = flag
    assert put(channel, {"quality": "720p", block: {key: value}}).status_code == 422
    assert snapshot(database) == before


@pytest.mark.parametrize(
    "payload",
    [
        [],
        True,
        {"recording": []},
        {"notifications": "bad"},
        {"recording": None},
        {"notifications": None},
        {"quality": "invalid-quality"},
        {"quality": {}},
        {"quality": 720},
        {"recording": {"quality": []}},
        {"recording": {"supported_codecs": "h264,invalid-codec"}},
        {"filenameTemplate": {}},
        {"supportedCodecs": []},
        {"maxStreams": -1},
        {"maxStreams": 1.5},
        {"maxStreams": "3"},
        {"autoRecord": "true"},
        {"useGlobalCleanupPolicy": 0},
        {"recording": {"enabled": False}, "autoRecord": True},
        {"recording": {"quality": "720p"}, "quality": "480p"},
        {"recording": {"custom_filename": "a"}, "filenameTemplate": "b"},
        {"recording": {"supported_codecs": "h265"}, "supportedCodecs": "av1"},
        {
            "recording": {"use_global_cleanup_policy": False},
            "useGlobalCleanupPolicy": True,
        },
        {"recording": {"max_streams": 1}, "maxStreams": 2},
    ],
)
def test_bad_shapes_and_conflicting_aliases_do_not_write(channel, payload):
    _, database, _ = channel
    before = snapshot(database)
    if isinstance(payload, dict):
        payload = {"notifications": {"notify_online": False}, **payload}
    assert put(channel, payload).status_code == 422
    assert snapshot(database) == before


def test_nested_and_legacy_partial_roundtrip(channel):
    client, database, auth = channel
    before = snapshot(database, unrelated=True)
    for value in (False, True):
        payload = {"recording": {}, "notifications": {}}
        for block, key in FLAGS:
            payload[block][key] = value
        response = put(channel, payload)
        assert response.status_code == 200, response.text
        read = client.get(PATH, headers=auth)
        assert read.status_code == 200, read.text
        readback = read.json()
        assert all(readback[block][key] is value for block, key in FLAGS)
    response = put(
        channel,
        {
            "autoRecord": False,
            "quality": "720p",
            "filenameTemplate": "{title}",
            "supportedCodecs": "av1,h264",
            "maxStreams": 0,
            "useGlobalCleanupPolicy": False,
            "recording": {"quality": "720p"},
            "notifications": {"notify_online": False},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "settings": {
            "autoRecord": False,
            "quality": "720p",
            "filenameTemplate": "{title}",
            "supportedCodecs": "av1,h264",
            "maxStreams": 0,
            "useGlobalCleanupPolicy": False,
        },
    }
    for payload in ({}, {"recording": {}, "notifications": {}}):
        saved = snapshot(database)
        assert put(channel, payload).json() == response.json()
        assert snapshot(database) == saved
    response = put(
        channel,
        {
            "filenameTemplate": "",
            "supportedCodecs": None,
            "maxStreams": None,
            "recording": {"quality": None, "custom_filename": None},
            "useGlobalCleanupPolicy": True,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["settings"] == {
        "autoRecord": False,
        "quality": None,
        "filenameTemplate": None,
        "supportedCodecs": None,
        "maxStreams": None,
        "useGlobalCleanupPolicy": True,
    }
    read = client.get(PATH, headers=auth)
    assert read.status_code == 200, read.text
    readback = read.json()
    assert readback["recording_quality"] is None
    assert readback["notifications"]["notify_online"] is False
    assert readback["notifications"]["notify_offline"] is True
    assert snapshot(database, unrelated=True) == before


def test_registered_openapi_describes_partial_strict_body(stack):  # noqa: F811
    app, *_ = stack
    doc = app.openapi()
    operation = doc["paths"]["/api/streamers/streamer/{streamer_id}/settings"]["put"]
    schemas = doc["components"]["schemas"]
    root = operation["requestBody"]["content"]["application/json"]["schema"]
    body = schemas[root["$ref"].split("/")[-1]]
    assert not body.get("required")
    properties = body["properties"]
    assert properties["autoRecord"]["type"] == "boolean"
    assert properties["useGlobalCleanupPolicy"]["type"] == "boolean"
    for block, key in FLAGS:
        fields = schemas[properties[block]["$ref"].split("/")[-1]]
        assert not fields.get("required")
        assert fields["properties"][key]["type"] == "boolean"
