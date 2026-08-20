"""Add durable Twitch upstream leases and their transaction guard."""

import logging

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    inspect,
    text,
)

from app.database import engine

logger = logging.getLogger("streamvault")


def _tables(metadata):
    Table("users", metadata, Column("id", Integer, primary_key=True))
    Table("recordings", metadata, Column("id", Integer, primary_key=True))
    state = Table(
        "twitch_upstream_coordination_state",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("lock_version", Integer, nullable=False, server_default="0"),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        CheckConstraint("id = 1", name="ck_twitch_upstream_coordination_singleton"),
    )
    leases = Table(
        "twitch_upstream_leases",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("channel_key", String(255), nullable=False),
        Column("auth_key", String(128), nullable=True),
        Column(
            "owner_user_id",
            Integer,
            ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        Column(
            "recording_id",
            Integer,
            ForeignKey("recordings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        Column("live_session_id", String(64), nullable=True),
        Column("purpose", String(16), nullable=False),
        Column("state", String(16), nullable=False),
        Column("generation", Integer, nullable=False),
        Column("process_pid", Integer, nullable=True),
        Column("process_group_id", Integer, nullable=True),
        Column("process_started_at", DateTime(timezone=True), nullable=True),
        Column("process_start_fingerprint", String(128), nullable=True),
        Column("reserved_at", DateTime(timezone=True), nullable=False),
        Column("activated_at", DateTime(timezone=True), nullable=True),
        Column("heartbeat_at", DateTime(timezone=True), nullable=False),
        Column("expires_at", DateTime(timezone=True), nullable=False),
        Column("released_at", DateTime(timezone=True), nullable=True),
        Column("release_reason", String(64), nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False),
        Column("updated_at", DateTime(timezone=True), nullable=False),
        CheckConstraint(
            "purpose IN ('RECORDING', 'LIVE', 'ROTATION', 'RECOVERY')",
            name="ck_twitch_upstream_leases_purpose",
        ),
        CheckConstraint(
            "state IN ('STARTING', 'ACTIVE', 'ROTATING', 'RECOVERING', 'RELEASED')",
            name="ck_twitch_upstream_leases_state",
        ),
    )
    Index(
        "ix_twitch_upstream_leases_state_expiry",
        leases.c.state,
        leases.c.expires_at,
    )
    Index("ix_twitch_upstream_leases_auth_state", leases.c.auth_key, leases.c.state)
    Index(
        "ix_twitch_upstream_leases_owner_state",
        leases.c.owner_user_id,
        leases.c.state,
    )
    Index("ix_twitch_upstream_leases_recording_id", leases.c.recording_id)
    Index(
        "uq_twitch_upstream_leases_channel_key",
        leases.c.channel_key,
        unique=True,
    )
    return state, leases


def upgrade(target_engine=None):
    target = target_engine or engine
    inspector = inspect(target)
    if "global_settings" in inspector.get_table_names() and not any(
        column["name"] == "twitch_max_concurrent_upstreams"
        for column in inspector.get_columns("global_settings")
    ):
        with target.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE global_settings ADD COLUMN "
                    "twitch_max_concurrent_upstreams INTEGER NOT NULL DEFAULT 5"
                )
            )

    metadata = MetaData()
    state, _leases = _tables(metadata)
    metadata.create_all(target, tables=[state, _leases], checkfirst=True)
    with target.begin() as connection:
        guard_exists = connection.execute(
            text("SELECT 1 FROM twitch_upstream_coordination_state WHERE id = 1")
        ).first()
        if not guard_exists:
            connection.execute(
                state.insert().values(
                    id=1, lock_version=0, updated_at=text("CURRENT_TIMESTAMP")
                )
            )
    logger.info("Migration 040: Twitch upstream coordination schema created")


def downgrade(target_engine=None):
    target = target_engine or engine
    metadata = MetaData()
    state, leases = _tables(metadata)
    with target.begin() as connection:
        if "twitch_upstream_leases" in inspect(connection).get_table_names():
            active_lease = connection.execute(
                text(
                    "SELECT 1 FROM twitch_upstream_leases "
                    "WHERE state IN ('STARTING', 'ACTIVE', 'ROTATING', 'RECOVERING') "
                    "LIMIT 1"
                )
            ).first()
            if active_lease:
                raise RuntimeError(
                    "Cannot downgrade while active Twitch upstream leases exist"
                )
            for index in list(leases.indexes):
                index.drop(connection, checkfirst=True)
            leases.drop(connection, checkfirst=True)
        state.drop(connection, checkfirst=True)
    logger.info("Migration 040: Twitch upstream coordination tables dropped")
