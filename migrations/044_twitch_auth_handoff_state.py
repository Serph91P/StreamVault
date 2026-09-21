"""Persist fenced Twitch authentication handoff state."""

import logging

from sqlalchemy import inspect, text

from app.database import engine

logger = logging.getLogger("streamvault")

COLUMNS = {
    "auth_priority": "INTEGER NOT NULL DEFAULT 0",
    "anonymous_available": "BOOLEAN NOT NULL DEFAULT TRUE",
    "auth_requested": "BOOLEAN NOT NULL DEFAULT FALSE",
    "handoff_target_channel": "VARCHAR(255)",
    "handoff_action": "VARCHAR(16)",
    "handoff_reason": "VARCHAR(64)",
    "handoff_requested_at": "TIMESTAMP WITH TIME ZONE",
    "partial_recording_warning": "BOOLEAN NOT NULL DEFAULT FALSE",
}


def upgrade(target_engine=None):
    target = target_engine or engine
    inspector = inspect(target)
    if "twitch_upstream_leases" not in inspector.get_table_names():
        logger.info("Migration 044 skipped: twitch_upstream_leases is absent")
        return
    existing = {
        column["name"] for column in inspector.get_columns("twitch_upstream_leases")
    }
    with target.begin() as connection:
        for name, definition in COLUMNS.items():
            if name not in existing:
                connection.execute(
                    text(
                        f"ALTER TABLE twitch_upstream_leases ADD COLUMN {name} {definition}"
                    )
                )
    logger.info("Migration 044: Twitch authentication handoff state added")


def downgrade(target_engine=None):
    target = target_engine or engine
    inspector = inspect(target)
    if "twitch_upstream_leases" not in inspector.get_table_names():
        return
    existing = {
        column["name"] for column in inspector.get_columns("twitch_upstream_leases")
    }
    with target.begin() as connection:
        for name in reversed(COLUMNS):
            if name in existing:
                connection.execute(
                    text(f"ALTER TABLE twitch_upstream_leases DROP COLUMN {name}")
                )
    logger.info("Migration 044: Twitch authentication handoff state removed")
