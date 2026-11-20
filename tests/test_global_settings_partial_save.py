"""The global settings endpoint persists only the submitted settings."""

import pytest
from sqlalchemy import select

from app.models import GlobalSettings
from app.services.notification_service import NotificationService
from app.services.system.streamlink_config_service import StreamlinkConfigService
from test_image_http_ownership import image_applications as image_applications


SETTINGS = "/api/settings"
SEED = {
    "notification_url": "ntfys://notify.invalid/topic",
    "notifications_enabled": True,
    "notify_online_global": False,
    "notify_offline_global": False,
    "notify_update_global": False,
    "notify_favorite_category_global": False,
    "notify_recording_started": True,
    "notify_recording_failed": False,
    "notify_recording_completed": True,
    "supported_codecs": "av1",
    "prefer_higher_quality": False,
    "twitch_max_concurrent_upstreams": 2,
    "http_proxy": "http://proxy.invalid:8080",
    "https_proxy": "https://proxy.invalid:8443",
    "proxy_encryption_key": "synthetic-internal-value",
}
PANEL_SAVE = {
    "notification_url": "ntfys://notify.invalid/topic",
    "notifications_enabled": False,
    "notify_online_global": False,
    "notify_offline_global": False,
    "notify_update_global": False,
    "notify_favorite_category_global": False,
    "notify_recording_started": True,
    "notify_recording_failed": False,
    "notify_recording_completed": True,
}
DOCS_URL = "https://github.com/caronc/apprise/wiki"


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_url", ["legacy-not-currently-valid", "  \t "])
async def test_panel_save_can_keep_unchanged_legacy_notification_url(
    image_applications, legacy_url
):
    _, databases, clients, _ = image_applications
    factory = databases[0].sync_session_factory

    seed = SEED | {"notification_url": legacy_url}
    with factory() as db:
        db.add(GlobalSettings(id=1, **seed))
        db.commit()

    client = clients[0]
    response = await client.post(
        SETTINGS, json=PANEL_SAVE | {"notification_url": legacy_url}
    )
    assert response.status_code == 200
    assert persisted(factory) == seed | {"notifications_enabled": False}


def persisted(session_factory):
    with session_factory() as db:
        row = db.scalars(select(GlobalSettings)).one()
        return {name: getattr(row, name) for name in SEED}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "initial_url", ["", SEED["notification_url"]], ids=["empty", "configured"]
)
async def test_whitespace_notification_url_rejects_entire_save(
    image_applications, monkeypatch, initial_url
):
    _, databases, clients, queries = image_applications
    factory = databases[0].sync_session_factory
    seed = SEED | {"notification_url": initial_url}
    with factory() as db:
        db.add(GlobalSettings(id=1, **seed))
        db.commit()

    effects = []
    monkeypatch.setattr(
        NotificationService, "_initialize_apprise", lambda _: effects.append("apprise")
    )

    async def regenerate(_service):
        effects.append("streamlink")
        return True

    monkeypatch.setattr(StreamlinkConfigService, "regenerate_config", regenerate)
    client = clients[0]
    before = await client.get(SETTINGS)
    assert before.status_code == 200
    queries.clear()
    response = await client.post(
        SETTINGS, json={"notification_url": "  \t ", "notify_update_global": True}
    )
    assert response.status_code == 500, response.text
    assert persisted(factory) == seed
    readback = await client.get(SETTINGS)
    assert readback.status_code == 200
    assert readback.json() == before.json()
    assert not effects
    assert not any(
        sql.lstrip().startswith("UPDATE global_settings") for _, sql in queries
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,changes,status,effects",
    [
        pytest.param(
            PANEL_SAVE, {"notifications_enabled": False}, 200, ["apprise"], id="panel"
        ),
        pytest.param({}, {}, 200, [], id="empty"),
        pytest.param(
            {"notify_recording_started": False},
            {"notify_recording_started": False},
            200,
            [],
            id="one-notification-field",
        ),
        pytest.param(
            {"supported_codecs": "h264,h265"},
            {"supported_codecs": "h264,h265"},
            200,
            ["streamlink"],
            id="codec-only-default",
        ),
        pytest.param(
            {"http_proxy": "http://other.invalid"},
            {"http_proxy": "http://other.invalid"},
            200,
            ["streamlink"],
            id="proxy-only",
        ),
        pytest.param(
            {"supported_codecs": "av1", "http_proxy": "http://proxy.invalid:8080"},
            {},
            200,
            [],
            id="identical",
        ),
        pytest.param(
            {
                "notification_url": "",
                "http_proxy": None,
                "https_proxy": "",
                "twitch_max_concurrent_upstreams": 5,
                "prefer_higher_quality": True,
            },
            {
                "notification_url": "",
                "http_proxy": "",
                "https_proxy": "",
                "twitch_max_concurrent_upstreams": 5,
                "prefer_higher_quality": True,
            },
            200,
            ["apprise", "streamlink"],
            id="explicit-clears-and-defaults",
        ),
        pytest.param(
            {"notification_url": None},
            {"notification_url": ""},
            200,
            ["apprise"],
            id="explicit-null-notification-url",
        ),
        pytest.param(
            {"http_proxy": "", "https_proxy": None, "supported_codecs": ""},
            {"http_proxy": "", "https_proxy": "", "supported_codecs": "h264,h265"},
            200,
            ["streamlink"],
            id="legacy-codec-normalization",
        ),
        pytest.param(
            {
                "id": 9,
                "apprise_docs_url": "https://other.invalid",
                "proxy_encryption_key": "ignored",
            },
            {},
            200,
            [],
            id="read-only-and-unknown",
        ),
        pytest.param(
            {"notifications_enabled": False, "http_proxy": "ftp://invalid.invalid"},
            {},
            500,
            [],
            id="invalid-proxy",
        ),
        pytest.param(
            {"notifications_enabled": False, "notification_url": "bad"},
            {},
            500,
            [],
            id="invalid-notification",
        ),
        pytest.param(
            {"notifications_enabled": False, "twitch_max_concurrent_upstreams": 0},
            {},
            422,
            [],
            id="invalid-limit",
        ),
    ],
)
async def test_global_settings_partial_save(
    image_applications, monkeypatch, payload, changes, status, effects
):
    _, databases, clients, queries = image_applications
    factory = databases[0].sync_session_factory
    with factory() as db:
        db.add(GlobalSettings(id=1, **SEED))
        db.commit()

    observed = []

    def initialize_apprise(_service):
        observed.append(("apprise", persisted(factory)))

    async def regenerate(_service):
        observed.append(("streamlink", persisted(factory)))
        return True

    monkeypatch.setattr(NotificationService, "_initialize_apprise", initialize_apprise)
    monkeypatch.setattr(StreamlinkConfigService, "regenerate_config", regenerate)
    client = clients[0]
    queries.clear()
    response = await client.post(SETTINGS, json=payload)
    assert response.status_code == status, response.text
    expected = SEED | changes
    assert persisted(factory) == expected
    readback = await client.get(SETTINGS)
    assert readback.status_code == 200
    public = {
        name: value
        for name, value in expected.items()
        if name != "proxy_encryption_key"
    }
    assert readback.json() == public | {"apprise_docs_url": DOCS_URL}
    if status == 200:
        assert response.json() == readback.json()
    assert observed == [(effect, expected) for effect in effects]
    if not changes:
        assert not any(
            sql.lstrip().startswith("UPDATE global_settings") for _, sql in queries
        )


@pytest.mark.asyncio
async def test_global_settings_empty_save_returns_fresh_defaults(
    image_applications, monkeypatch
):
    _, databases, clients, _ = image_applications

    def no_side_effect(_service):
        pytest.fail("no effective settings change should trigger a side effect")

    monkeypatch.setattr(NotificationService, "_initialize_apprise", no_side_effect)
    monkeypatch.setattr(StreamlinkConfigService, "regenerate_config", no_side_effect)
    response = await clients[0].post(SETTINGS, json={})
    assert response.status_code == 200
    readback = await clients[0].get(SETTINGS)
    assert readback.status_code == 200
    assert response.json() == readback.json()
    assert response.json()["notification_url"] == ""
    assert response.json()["notifications_enabled"] is True
    assert response.json()["supported_codecs"] == "h264,h265"
    assert response.json()["prefer_higher_quality"] is True
    assert response.json()["twitch_max_concurrent_upstreams"] == 5
    assert response.json()["http_proxy"] == response.json()["https_proxy"] == ""
    assert (
        persisted(databases[0].sync_session_factory)["supported_codecs"] == "h264,h265"
    )
    same_effect = await clients[0].post(
        SETTINGS,
        json={"http_proxy": None, "https_proxy": "  ", "supported_codecs": ""},
    )
    assert same_effect.status_code == 200
    assert same_effect.json()["supported_codecs"] == "h264,h265"
    row = persisted(databases[0].sync_session_factory)
    assert row["http_proxy"] == ""
    assert row["https_proxy"] == "  "
