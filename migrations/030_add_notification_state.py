"""
Migration 030: Add notification_state table for persistent notification tracking

This migration adds a new table to track notification read/clear state per user,
enabling persistent notification management across sessions.
"""

from sqlalchemy import text
from app.database import engine
import logging

logger = logging.getLogger(__name__)


def upgrade():
    """Create notification_state table"""
    with engine.begin() as connection:
        # Create notification_state table
        connection.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS notification_state (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                last_read_timestamp TIMESTAMP WITH TIME ZONE,
                last_cleared_timestamp TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """
            )
        )

        # Create index on user_id for fast lookups
        connection.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_notification_state_user_id
            ON notification_state(user_id)
        """
            )
        )

        logger.info("✅ Created notification_state table with user_id index")


def downgrade():
    """Drop notification_state table"""
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS notification_state CASCADE"))
        logger.info("✅ Dropped notification_state table")


if __name__ == "__main__":
    upgrade()
