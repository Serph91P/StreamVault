"""
Add episode_number column to streams table

This migration adds the episode_number column to the streams table
to track episode numbers persistently in the database.
"""

from app.database import engine
from sqlalchemy import text
import logging

logger = logging.getLogger("streamvault")


def upgrade():
    """Add episode_number column to streams table"""
    try:
        with engine.connect() as conn:
            # Check if column already exists (PostgreSQL)
            try:
                result = conn.execute(
                    text(
                        """
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_name = 'streams'
                    AND column_name = 'episode_number'
                """
                    )
                )

                if result.scalar() > 0:
                    logger.info("Column episode_number already exists in streams table")
                    return
            except Exception:
                # Fallback for SQLite or other databases
                pass

            # Add the episode_number column
            conn.execute(text("ALTER TABLE streams ADD COLUMN episode_number INTEGER"))
            conn.commit()
            logger.info("Successfully added episode_number column to streams table")
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
            logger.info("Column episode_number already exists in streams table")
        else:
            logger.error(f"Error adding episode_number column: {e}")
            raise


def downgrade():
    """Remove episode_number column from streams table"""
    try:
        with engine.connect() as conn:
            # Remove the episode_number column
            conn.execute(text("ALTER TABLE streams DROP COLUMN episode_number"))
            conn.commit()
            logger.info("Successfully removed episode_number column from streams table")
    except Exception as e:
        logger.error(f"Error removing episode_number column: {e}")
        raise


if __name__ == "__main__":
    upgrade()
