"""Additive delivery identity: real legacy rows, restart, and competing commits."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from threading import Barrier
from uuid import uuid4

from alembic import command
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import StreamEvent
from app.services.system.migration_service import MigrationService


@pytest.fixture(params=["sqlite", "postgres"])
def migrated_events(request, tmp_path):
    schema = None
    if request.param == "postgres":
        url = os.environ.get("SV1029_POSTGRES_URL")
        if not url:
            pytest.skip("requires task-owned SV1029_POSTGRES_URL")
        admin = create_engine(url, isolation_level="AUTOCOMMIT")
        schema = "sv1029_" + uuid4().hex
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{schema}"'))
        engine = create_engine(make_url(url).set(database=schema))
        migrations = MigrationService.for_engine(engine)
        migrations.ensure_migrations_table()
        results = migrations._run_pending_migrations()
        assert len(results) == 48
        assert all(success for _, success, _ in results), results
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO streamers (id,twitch_id,username) VALUES (1,'synthetic-1029','synthetic-1029')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO streams (id,streamer_id,twitch_stream_id) VALUES (1,1,'synthetic-1029-stream')"
                )
            )
    else:
        engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
        migrations = MigrationService.for_engine(engine)
        # Numbered legacy DDL contains PostgreSQL functions; this is its SQLite table equivalent.
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE streams (id INTEGER PRIMARY KEY)"))
            connection.execute(text("INSERT INTO streams VALUES (1)"))
            connection.execute(
                text(
                    "CREATE TABLE stream_events (id INTEGER PRIMARY KEY, stream_id INTEGER REFERENCES streams(id), event_type VARCHAR(100) NOT NULL, title VARCHAR(500), category_name VARCHAR(100), language VARCHAR(10), timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
                )
            )
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO stream_events (id,stream_id,event_type,title) VALUES (101,1,'channel.update','legacy chapter'), (102,1,'channel.update','second legacy chapter')"
            )
        )
        config = migrations._alembic_config(connection)
        if request.param == "postgres":
            command.stamp(config, migrations.ALEMBIC_LEGACY_BASELINE)
            command.upgrade(config, "20261106_tasks")
        else:
            command.stamp(config, "20261106_tasks")
    try:
        migrations._upgrade_alembic()
        yield engine, migrations
    finally:
        engine.dispose()
        if schema:
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE "{schema}"'))
            admin.dispose()


def test_delivery_migration_preserves_legacy_and_uniqueness_after_restart(
    migrated_events,
):
    engine, migrations = migrated_events
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT id,title,delivery_key FROM stream_events ORDER BY id")
        ).all() == [(101, "legacy chapter", None), (102, "second legacy chapter", None)]
    assert (
        next(
            c
            for c in inspect(engine).get_columns("stream_events")
            if c["name"] == "delivery_key"
        )["nullable"]
        is True
    )
    assert next(
        i
        for i in inspect(engine).get_indexes("stream_events")
        if i["name"] == "ix_stream_events_delivery_key"
    )["unique"]
    migrations._upgrade_alembic()
    engine.dispose()  # New connections after a completed schema restart.
    sessions = sessionmaker(bind=engine)
    barrier = Barrier(2)

    def deliver(identity):
        with sessions() as session:
            session.add(
                StreamEvent(
                    id=identity,
                    stream_id=1,
                    event_type="channel.update",
                    title="new chapter",
                    timestamp=datetime.now(timezone.utc),
                    delivery_key="a" * 64,
                )
            )
            barrier.wait(timeout=10)
            try:
                session.commit()
                return "committed"
            except IntegrityError:
                session.rollback()
                return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(deliver, [201, 202])) == ["committed", "duplicate"]
    with sessions() as session:
        session.add_all(
            [
                StreamEvent(
                    id=203,
                    stream_id=1,
                    event_type="channel.update",
                    delivery_key="b" * 64,
                ),
                StreamEvent(
                    id=204, stream_id=1, event_type="channel.update", delivery_key=None
                ),
            ]
        )
        session.commit()
        assert session.query(StreamEvent).count() == 5
        assert (
            session.query(StreamEvent)
            .filter(StreamEvent.delivery_key.is_(None))
            .count()
            == 3
        )
    migrations._upgrade_alembic()
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT count(*) FROM stream_events")).scalar_one()
            == 5
        )
        assert (
            connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            == "20261116_eventsub"
        )
