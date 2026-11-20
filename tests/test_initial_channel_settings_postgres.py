"""Real first-save races on fresh databases; use a disposable SV1031_POSTGRES_URL."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, local
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, sessionmaker

from app.database import Base
from app.models import (
    GlobalSettings,
    NotificationSettings,
    Streamer,
    StreamerRecordingSettings,
)
from app.routes import recording, settings, streamers
from app.schemas.recording import StreamerRecordingSettingsUpdate
from app.schemas.settings import (
    StreamerNotificationSettingsSchema,
    StreamerNotificationSettingsUpdateSchema,
)
from app.services.core.settings_service import SettingsService
from app.services.notifications.push_notification_service import PushNotificationService
from app.services.streamers.streamer_repository import StreamerRepository
from app.services.system.migration_service import MigrationService


@pytest.fixture(scope="module", params=["migrated", "orm"])
def postgres(request):
    value = os.getenv("SV1031_POSTGRES_URL")
    if not value:
        pytest.skip(
            "requires disposable SV1031_POSTGRES_URL with CREATE DATABASE access"
        )
    url = make_url(value)
    assert url.get_backend_name() == "postgresql"
    name = "sv1031_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(
        url.set(database=name), connect_args={"options": "-c statement_timeout=15000"}
    )
    migrations = MigrationService.for_engine(engine)
    try:
        assert not inspect(engine).get_table_names()
        if request.param == "migrated":
            assert migrations.run_safe_migrations()
        else:
            Base.metadata.create_all(engine)
        yield engine, migrations if request.param == "migrated" else None
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}"'))
        admin.dispose()


def _seed(engine):
    with Session(engine) as db:
        channels = [
            Streamer(username=uuid4().hex, twitch_id=uuid4().hex) for _ in range(2)
        ]
        db.add_all(channels)
        db.flush()
        ids = tuple(channel.id for channel in channels)
        db.add(NotificationSettings(streamer_id=ids[1], notify_online=False))
        db.add(
            StreamerRecordingSettings(streamer_id=ids[1], enabled=False, quality="360p")
        )
        if db.get(GlobalSettings, 1) is None:
            db.add(GlobalSettings(id=1))
        db.flush()
        global_row = db.get(GlobalSettings, 1)
        global_row.notifications_enabled = True
        global_row.notify_online_global = True
        db.commit()
        return ids


def _snapshot(engine, model, channel_id):
    with Session(engine) as db:
        return (
            db.execute(select(model.__table__).where(model.streamer_id == channel_id))
            .mappings()
            .all()
        )


@pytest.mark.parametrize("model", [NotificationSettings, StreamerRecordingSettings])
def test_single_row_invariant_rejects_real_duplicate(postgres, model):
    engine, _ = postgres
    _, existing = _seed(engine)
    table = model.__tablename__
    constraints = inspect(engine).get_unique_constraints(table)
    before = _snapshot(engine, model, existing)
    with Session(engine) as db, pytest.raises(IntegrityError) as error:
        db.add(model(streamer_id=existing))
        db.commit()
    assert error.value.orig.sqlstate == "23505"
    assert any(item["column_names"] == ["streamer_id"] for item in constraints)
    assert _snapshot(engine, model, existing) == before


IMAGE = SimpleNamespace(get_profile_image_url=lambda *_: None)
LOG = SimpleNamespace(log_configuration_change=lambda *_: None)


def _call(kind, sessions, db, channel, value):
    svc = SettingsService(db)
    if kind == "notification":
        body = StreamerNotificationSettingsUpdateSchema(notify_online=value)
        return settings.update_streamer_settings(
            channel, body, svc, IMAGE, None
        ).streamer_id
    if kind == "notification_service_save":
        return asyncio.run(
            svc.update_streamer_settings(
                channel,
                StreamerNotificationSettingsSchema(
                    streamer_id=channel, notify_online=value
                ),
            )
        ).streamer_id
    if kind == "notification_service_get":
        return asyncio.run(svc.get_streamer_settings(channel)).streamer_id
    if kind == "notification_repo":
        return (
            StreamerRepository(db)
            .update_notification_settings(channel, notify_online=value)
            .streamer_id
        )
    if kind == "recording_repo":
        return (
            StreamerRepository(db)
            .update_recording_settings(channel, enabled=value)
            .streamer_id
        )
    if kind == "nested_notification":
        return streamers.update_streamer_settings(
            channel, {"notifications": {"notify_online": value}}, db
        )["success"]
    if kind == "nested_recording":
        return streamers.update_streamer_settings(
            channel, {"recording": {"enabled": value}}, db
        )["success"]
    if kind == "add_recording":
        streamer = db.get(Streamer, channel)
        lookup = SimpleNamespace(add_streamer=AsyncMock(return_value=streamer))
        return asyncio.run(
            streamers.add_streamer(
                streamer.username, {"recording": {"enabled": value}}, lookup, db, IMAGE
            )
        )["id"]
    if kind == "recording_save":
        update = StreamerRecordingSettingsUpdate(streamer_id=channel, enabled=value)
        return recording.update_streamer_recording_settings(
            channel, update, db, LOG, IMAGE
        ).streamer_id
    if kind == "cleanup_save":
        return recording.update_streamer_cleanup_policy(
            channel, {"use_global_cleanup_policy": value}, db
        )["status"]
    assert kind == "recording_list"
    rows = recording.get_all_streamer_recording_settings(sessions, IMAGE)
    return next(row.enabled for row in rows if row.streamer_id == channel)


@pytest.mark.parametrize(
    ("left", "right", "model", "field"),
    [
        ("notification", "notification", NotificationSettings, "notify_online"),
        (
            "notification_service_save",
            "notification_service_save",
            NotificationSettings,
            "notify_online",
        ),
        (
            "notification_service_get",
            "notification",
            NotificationSettings,
            "notify_online",
        ),
        (
            "notification_repo",
            "notification_repo",
            NotificationSettings,
            "notify_online",
        ),
        ("nested_notification", "notification", NotificationSettings, "notify_online"),
        ("nested_recording", "recording_save", StreamerRecordingSettings, "enabled"),
        ("add_recording", "recording_save", StreamerRecordingSettings, "enabled"),
        ("recording_repo", "recording_repo", StreamerRecordingSettings, "enabled"),
        (
            "cleanup_save",
            "cleanup_save",
            StreamerRecordingSettings,
            "use_global_cleanup_policy",
        ),
        ("recording_list", "recording_save", StreamerRecordingSettings, "enabled"),
        ("recording_list", "recording_list", StreamerRecordingSettings, "enabled"),
    ],
)
def test_initial_settings_overlap(postgres, monkeypatch, left, right, model, field):
    engine, _ = postgres
    channel, existing = _seed(engine)
    if left == "nested_notification":
        with Session(engine) as db:
            db.add(StreamerRecordingSettings(streamer_id=channel))
            db.commit()
    before = _snapshot(engine, model, existing)
    global_before = _snapshot_global(engine)
    sessions = sessionmaker(engine)
    ready = Barrier(2, timeout=10)
    first_committing = Event()
    worker = local()
    seen = set()
    backend_pids = set()
    first, all_rows = Query.first, Query.all

    def wait(query, missing):
        if (
            query.column_descriptions[0]["entity"] is model
            and missing
            and query.session not in seen
        ):
            seen.add(query.session)
            backend_pids.add(
                query.session.connection()
                .exec_driver_sql("SELECT pg_backend_pid()")
                .scalar_one()
            )
            ready.wait()
            if not worker.first:
                assert first_committing.wait(timeout=10)

    def first_after_lookup(query):
        row = first(query)
        wait(query, row is None)
        return row

    def all_after_lookup(query):
        rows = all_rows(query)
        if query.column_descriptions[0]["entity"] is model:
            wait(query, not any(row.streamer_id == channel for row in rows))
        return rows

    def before_commit(db):
        if worker.first:
            # The first writer holds its DB lock when the stale lookup resumes.
            db.flush()
            first_committing.set()

    def invoke(kind, value):
        worker.first = value
        with sessions() as db:
            return _call(kind, sessions, db, channel, value)

    with monkeypatch.context() as patch:
        patch.setattr(Query, "first", first_after_lookup)
        patch.setattr(Query, "all", all_after_lookup)
        patch.setattr(streamers, "emit_toast", AsyncMock())
        patch.setattr(streamers, "emit_event", AsyncMock())
        event.listen(sessions, "before_commit", before_commit)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                calls = [
                    pool.submit(invoke, left, True),
                    pool.submit(invoke, right, False),
                ]
                for call in calls:
                    call.result(timeout=20)
        finally:
            event.remove(sessions, "before_commit", before_commit)
    assert len(seen) == 2
    assert len(backend_pids) == 2
    rows = _snapshot(engine, model, channel)
    assert len(rows) == 1
    assert _snapshot(engine, model, existing) == before
    assert _snapshot_global(engine) == global_before
    value = rows[0][field]
    assert value is (
        right == "recording_list"
    )  # The second writer wins; a list only initializes defaults.
    if model is NotificationSettings:
        with sessions() as db:
            [listed] = [
                row
                for row in SettingsService(db).get_streamer_settings_flat()
                if row["streamer_id"] == channel
            ]
        policy = PushNotificationService(session_factory=sessions)
        assert listed[field] is value
        assert asyncio.run(policy.should_notify(channel, "online")) is value


def _snapshot_global(engine):
    with Session(engine) as db:
        return db.execute(select(GlobalSettings.__table__)).all()


def test_repeat_startup_preserves_existing_rows(postgres):
    engine, migrations = postgres
    _, existing = _seed(engine)
    models = [NotificationSettings, StreamerRecordingSettings]
    before = [_snapshot(engine, model, existing) for model in models]
    global_before = _snapshot_global(engine)
    if migrations:
        assert migrations.run_safe_migrations()
    else:
        Base.metadata.create_all(engine)
    assert [_snapshot(engine, model, existing) for model in models] == before
    assert _snapshot_global(engine) == global_before
