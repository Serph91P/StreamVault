"""
Migration 017: Enable Session Management and Cleanup

This migration adds session cleanup functionality to resolve video sharing
authentication failures in multi-user production environments.
"""

import logging
from sqlalchemy import text
from app.database import get_db
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("streamvault")


def upgrade():
    """Enable session management and cleanup"""
    db = next(get_db())
    try:
        logger.info("Migration 017: Enabling session management and cleanup")

        # Clean up any existing sessions older than 30 days to start fresh
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        # Count sessions to be cleaned
        result = db.execute(
            text(
                """
            SELECT COUNT(*) as count
            FROM sessions
            WHERE created_at < :cutoff_date
        """
            ),
            {"cutoff_date": cutoff_date},
        )

        old_session_count = result.fetchone()[0]

        if old_session_count > 0:
            logger.info(f"Cleaning up {old_session_count} sessions older than 30 days")

            # Delete old sessions
            db.execute(
                text(
                    """
                DELETE FROM sessions
                WHERE created_at < :cutoff_date
            """
                ),
                {"cutoff_date": cutoff_date},
            )

            db.commit()
            logger.info(f"Successfully cleaned up {old_session_count} old sessions")
        else:
            logger.info("No old sessions to clean up")

        # Add index on created_at for efficient cleanup queries if not exists
        try:
            db.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_sessions_created_at
                ON sessions(created_at)
            """
                )
            )
            db.commit()
            logger.info("Added index on sessions.created_at for efficient cleanup")
        except Exception as e:
            logger.warning(f"Could not create index (may already exist): {e}")
            db.rollback()

        # Get final session count
        result = db.execute(text("SELECT COUNT(*) as count FROM sessions"))
        final_session_count = result.fetchone()[0]

        logger.info(f"Migration 017 completed successfully. Active sessions: {final_session_count}")

    except Exception as e:
        logger.error(f"Migration 017 failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def downgrade():
    """Downgrade migration (remove index)"""
    db = next(get_db())
    try:
        logger.info("Migration 017 downgrade: Removing session cleanup optimizations")

        # Remove the index
        try:
            db.execute(text("DROP INDEX IF EXISTS idx_sessions_created_at"))
            db.commit()
            logger.info("Removed sessions.created_at index")
        except Exception as e:
            logger.warning(f"Could not remove index: {e}")
            db.rollback()

        logger.info("Migration 017 downgrade completed")

    except Exception as e:
        logger.error(f"Migration 017 downgrade failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
