"""Retention safety at real API, SQLite, filesystem and scheduler boundaries."""

import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import select

from app.database import Base
from app.dependencies import get_retention_service
from app.lifespan import _run_recording_cleanup
from app.models import Recording, RecordingSettings, Stream, StreamerRecordingSettings
from tests.test_recording_capabilities import headers, stack  # noqa: F401


@pytest.fixture
def retention(stack):  # noqa: F811
    app, database, settings, client, tmp_path = stack
    media = tmp_path / "recordings" / "synthetic" / "Season 2026"
    media.mkdir(parents=True)
    with database.sync_session_factory() as db:
        for identifier in (1, 2, 3):
            path = media / f"episode-{identifier}.mp4"
            path.write_bytes(b"synthetic recording")
            started = datetime.now(timezone.utc) - timedelta(days=5 - identifier)
            db.add(
                Stream(
                    id=identifier,
                    streamer_id=1,
                    started_at=started,
                    ended_at=started + timedelta(hours=1),
                    recording_path=str(path),
                )
            )
            db.flush()
            db.add(
                Recording(
                    stream_id=identifier,
                    path=str(path),
                    status="completed",
                    start_time=started,
                )
            )
        db.commit()
    return app, database, settings, client, media, headers(stack, "jwt", "admin")


def snapshot(retention):
    _, database, _, _, media, _ = retention
    with database.sync_session_factory() as db:
        rows = {
            table.name: db.execute(select(table)).all()
            for table in Base.metadata.sorted_tables
        }
    return rows, {p.name: p.read_bytes() for p in media.glob("*.mp4")}


def request_policy(retention, entry, policy, **outer):
    _, _, _, client, media, auth = retention
    endpoint, body = {
        "global": (
            "settings",
            {"output_directory": str(media.parent.parent), "cleanup_policy": policy},
        ),
        "channel": ("streamers/1", {"streamer_id": 1, "cleanup_policy": policy}),
        "policy-save": ("streamers/1/cleanup-policy", {"cleanup_policy": policy}),
        "custom": ("cleanup/1/custom", policy),
    }[entry]
    return client.post(
        f"/api/recording/{endpoint}", json={**body, **outer}, headers=auth
    )


MAX_DAYS = datetime.now(timezone.utc).toordinal() - 1
BOUNDS = [("count", 2**31 - 1), ("size", 2**33 - 1), ("age", MAX_DAYS)]


@pytest.mark.parametrize("entry", ["global", "channel", "policy-save", "custom"])
@pytest.mark.parametrize("kind,maximum", BOUNDS)
@pytest.mark.parametrize(
    "case",
    [
        "negative",
        "zero",
        "min",
        "max",
        "overflow",
        "wrong-type",
        "coercible",
        "preservation",
    ],
)
def test_policy_boundaries_and_effects(retention, entry, kind, maximum, case):
    value = {
        "negative": -1,
        "zero": 0,
        "min": 1,
        "max": maximum,
        "overflow": maximum + 1,
        "wrong-type": [],
        "coercible": "1",
        "preservation": 1,
    }[case]
    policy = {
        "type": kind,
        "threshold": value,
        "preserve_favorites": "false" if case == "preservation" else False,
    }
    before = snapshot(retention)
    response = request_policy(retention, entry, policy)
    after = snapshot(retention)
    if case not in {"min", "max"}:
        assert response.status_code == 422, response.text
        assert after == before
    elif entry == "custom":
        assert response.status_code == 200, response.text
        removed = {"age": 3, "count": 2, "size": 0}[kind] if case == "min" else 0
        assert response.json()["deleted_count"] == removed
        assert (
            len(after[1])
            == len(after[0]["streams"])
            == len(after[0]["recordings"])
            == 3 - removed
        )
        assert after[0]["background_tasks"] == before[0]["background_tasks"]
    else:
        assert response.status_code == 200, response.text
        model = RecordingSettings if entry == "global" else StreamerRecordingSettings
        with retention[1].sync_session_factory() as db:
            saved = json.loads(db.get(model, 1).cleanup_policy)
            assert all(saved[key] == expected for key, expected in policy.items())
        assert after[1] == before[1]
        assert after[0]["background_tasks"] == before[0]["background_tasks"]


@pytest.mark.parametrize("entry", ["global", "channel", "raw-channel"])
@pytest.mark.parametrize("value", [-1, 0, 1, 2**31 - 1, 2**31, True, 1.5, "1"])
def test_legacy_count_save_boundary(retention, entry, value):
    before = snapshot(retention)
    _, database, settings, client, _, auth = retention
    if entry == "raw-channel":
        response = client.put(
            "/api/streamers/streamer/1/settings",
            json={"maxStreams": value},
            headers=auth,
        )
    elif entry == "global":
        response = client.post(
            "/api/recording/settings",
            json={
                "output_directory": settings.RECORDING_DIRECTORY,
                "max_streams_per_streamer": value,
            },
            headers=auth,
        )
    else:
        response = client.post(
            "/api/recording/streamers/1",
            json={"streamer_id": 1, "max_streams": value},
            headers=auth,
        )
    if type(value) is not int or not 0 <= value <= 2**31 - 1:
        assert response.status_code == 422, response.text
        assert snapshot(retention) == before
    else:
        assert response.status_code == 200, response.text
        with database.sync_session_factory() as db:
            if entry == "global":
                assert db.get(RecordingSettings, 1).max_streams_per_streamer == value
            else:
                assert db.get(StreamerRecordingSettings, 1).max_streams == value


@pytest.mark.parametrize("source", ["global", "channel"])
@pytest.mark.parametrize(
    "stored",
    [
        "not JSON",
        "null",
        "{}",
        "[]",
        "false",
        '""',
        "",
        '{"type":"count","threshold":-1}',
        '{"type":"size","threshold":-1}',
        '{"type":"age","threshold":-1}',
        '{"type":"age","threshold":0}',
        '{"type":"age","threshold":99999999}',
        '{"type":"count","threshold":true}',
        '{"type":"custom","threshold":1}',
        '{"type":"age","threshold":1,"preserve_favorites":"false"}',
        '{"type":"age","threshold":1,"preserve_timeframe":{"weekdays":[7]}}',
        -1,
        "invalid-integer",
        2**31,
    ],
)
@pytest.mark.asyncio
async def test_invalid_legacy_policy_refuses_manual_and_scheduled_cleanup(
    retention, source, stored, caplog, monkeypatch
):
    _, database, settings, client, _, auth = retention
    with database.sync_session_factory() as db:
        global_settings = db.get(RecordingSettings, 1)
        channel = db.get(StreamerRecordingSettings, 1)
        channel.use_global_cleanup_policy = source == "global"
        global_settings.max_streams_per_streamer = (
            1  # Fail closed, not a destructive fallback.
        )
        if isinstance(stored, int) or stored == "invalid-integer":
            if source == "global":
                global_settings.max_streams_per_streamer = stored
            else:
                channel.max_streams = stored
        elif source == "global":
            global_settings.cleanup_policy = stored
        else:
            channel.cleanup_policy = stored
        db.commit()
    before = snapshot(retention)
    response = await asyncio.to_thread(
        client.post, "/api/recording/cleanup/1", headers=auth
    )
    assert response.status_code == 409, response.text
    assert source in response.json()["detail"]
    assert snapshot(retention) == before

    async def stop_after_one_cycle(_):
        raise asyncio.CancelledError

    monkeypatch.setattr("app.lifespan.asyncio.sleep", stop_after_one_cycle)
    with pytest.raises(asyncio.CancelledError):
        await _run_recording_cleanup(database.sync_session_factory, settings)
    assert snapshot(retention) == before
    assert any(
        "Invalid" in record.message and source in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize(
    "kind,threshold,expected", [("age", 1, {4}), ("count", 1, {4}), ("size", 1, {4, 5})]
)
@pytest.mark.asyncio
async def test_preview_and_execute_agree_with_protection_and_recent_filter(
    retention, kind, threshold, expected
):
    app, database, _, _, media, _ = retention
    from starlette.requests import HTTPConnection
    from app.models import Category, FavoriteCategory, User

    with database.sync_session_factory() as db:
        user = db.query(User).first()
        db.add(Category(id=10, name="Favorite", twitch_id="synthetic-favorite"))
        db.flush()
        db.add(FavoriteCategory(user_id=user.id, category_id=10))
        for i in range(1, 8):
            row = db.get(Stream, i)
            path = media / f"episode-{i}.mp4"
            with path.open("wb") as file:
                file.truncate(512 * 1024 * 1024)
            started = datetime(2020, 1, 5 + i, 10, tzinfo=timezone.utc)
            if not row:
                row = Stream(id=i, streamer_id=1, recording_path=str(path))
                db.add(row)
            row.started_at = (
                started if i != 5 else datetime.now(timezone.utc) - timedelta(hours=2)
            )
            row.ended_at = (
                datetime.now(timezone.utc) - timedelta(minutes=1)
                if i == 6
                else None
                if i == 7
                else row.started_at + timedelta(hours=1)
            )
            row.category_name = {1: "Favorite", 2: "Protected"}.get(i)
        db.commit()
    service = get_retention_service(HTTPConnection({"type": "http", "app": app}))
    policy = {
        "type": kind,
        "threshold": threshold,
        "preserve_favorites": True,
        "preserve_categories": ["Protected"],
        "preserve_timeframe": {"start_date": "2020-01-08", "end_date": "2020-01-09"},
    }
    count, preview = await service.simulate_cleanup(1, policy)
    assert (
        count == len(expected)
        and {item["id"] for item in preview["streams"]} == expected
    )
    assert all((media / f"episode-{i}.mp4").exists() for i in range(1, 8))
    deleted, paths = await service.cleanup_old_recordings(1, policy)
    assert deleted == count
    assert set(paths) == {str(media / f"episode-{i}.mp4") for i in expected}
    with database.sync_session_factory() as db:
        assert set(db.scalars(select(Stream.id))) == set(range(1, 8)) - expected
    assert {
        i for i in range(1, 8) if not (media / f"episode-{i}.mp4").exists()
    } == expected
