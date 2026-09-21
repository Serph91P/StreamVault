"""Add bounded per-streamer Twitch authentication priority."""

import logging

from sqlalchemy import inspect, text

from app.database import engine

logger = logging.getLogger("streamvault")

COLUMN = "twitch_auth_priority"
CONSTRAINT = "ck_streamer_recording_settings_twitch_auth_priority"


def upgrade(target_engine=None):
    target = target_engine or engine
    inspector = inspect(target)
    if "streamer_recording_settings" not in inspector.get_table_names():
        logger.info("Migration 043 skipped: streamer_recording_settings is absent")
        return

    columns = {column["name"] for column in inspector.get_columns("streamer_recording_settings")}
    if COLUMN not in columns:
        with target.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE streamer_recording_settings ADD COLUMN "
                    "twitch_auth_priority INTEGER NOT NULL DEFAULT 0"
                )
            )

    if target.dialect.name == "postgresql":
        constraints = {
            constraint.get("name")
            for constraint in inspect(target).get_check_constraints(
                "streamer_recording_settings"
            )
        }
        if CONSTRAINT not in constraints:
            with target.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE streamer_recording_settings ADD CONSTRAINT "
                        f"{CONSTRAINT} CHECK "
                        "(twitch_auth_priority BETWEEN -1000 AND 1000)"
                    )
                )

    logger.info("Migration 043: Twitch authentication priority added")


def downgrade(target_engine=None):
    target = target_engine or engine
    inspector = inspect(target)
    if "streamer_recording_settings" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("streamer_recording_settings")}
    if COLUMN not in columns:
        return
    with target.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE streamer_recording_settings "
                "DROP COLUMN twitch_auth_priority"
            )
        )
    logger.info("Migration 043: Twitch authentication priority removed")
