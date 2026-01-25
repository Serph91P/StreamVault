"""
Add CASCADE constraint to active_recordings_state.stream_id

This migration adds ON DELETE CASCADE to the stream_id foreign key in the
active_recordings_state table to prevent constraint violations when deleting streams.
"""

from app.database import engine
from sqlalchemy import text
import logging

logger = logging.getLogger("streamvault")


def upgrade():
    """Add CASCADE constraint to active_recordings_state.stream_id"""
    logger.info("🔄 Adding CASCADE constraint to active_recordings_state.stream_id...")

    with engine.connect() as connection:
        # First check if the table exists
        table_exists = connection.execute(
            text(
                """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'active_recordings_state'
            );
        """
            )
        ).scalar()

        if not table_exists:
            logger.info("Table active_recordings_state does not exist yet, skipping cascade constraint...")
            return

        # Check if the constraint already exists
        result = connection.execute(
            text(
                """
            SELECT conname
            FROM pg_constraint
            WHERE conname = 'active_recordings_state_stream_id_fkey'
            AND contype = 'f';
        """
            )
        ).fetchone()

        if result:
            logger.info("Dropping existing foreign key constraint...")
            # Drop the existing foreign key constraint
            connection.execute(
                text(
                    """
                ALTER TABLE active_recordings_state
                DROP CONSTRAINT active_recordings_state_stream_id_fkey;
            """
                )
            )
            connection.commit()

        # Add the new foreign key constraint with CASCADE
        logger.info("Adding new foreign key constraint with CASCADE...")
        connection.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD CONSTRAINT active_recordings_state_stream_id_fkey
            FOREIGN KEY (stream_id) REFERENCES streams(id) ON DELETE CASCADE;
        """
            )
        )
        connection.commit()

        logger.info("✅ CASCADE constraint added successfully")


def downgrade():
    """Remove CASCADE constraint from active_recordings_state.stream_id"""
    logger.info("🔄 Removing CASCADE constraint from active_recordings_state.stream_id...")

    with engine.connect() as connection:
        # Drop the CASCADE constraint
        connection.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            DROP CONSTRAINT IF EXISTS active_recordings_state_stream_id_fkey;
        """
            )
        )
        connection.commit()

        # Add back the original foreign key constraint (without CASCADE)
        connection.execute(
            text(
                """
            ALTER TABLE active_recordings_state
            ADD CONSTRAINT active_recordings_state_stream_id_fkey
            FOREIGN KEY (stream_id) REFERENCES streams(id);
        """
            )
        )
        connection.commit()

        logger.info("✅ CASCADE constraint removed successfully")
