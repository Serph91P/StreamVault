"""
Migration 036: Add Streamer Description (Twitch Bio)

Adds a `description` column to the streamers table which stores the streamer's
Twitch "About" / bio text. This is used in NFO files (tvshow.nfo <plot>) so that
Plex/Emby/Jellyfin show the real channel description instead of a generic
"Streams by X on Twitch." placeholder.

The Twitch Helix /users endpoint already returns this field as `description`;
we simply persist it for NFO generation and frontend display.
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


def run_migration():
    """Add description column to streamers table (idempotent)."""

    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration 036: Add Streamer Description")

            check_result = session.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'streamers'
                      AND column_name = 'description'
                    """
                )
            ).fetchone()

            if check_result:
                logger.info("✅ Column 'description' already exists, skipping")
            else:
                session.execute(
                    text(
                        """
                        ALTER TABLE streamers
                        ADD COLUMN description TEXT
                        """
                    )
                )
                logger.info("✅ Added 'description' column to streamers table")

            session.commit()
            logger.info("✅ Migration 036 completed successfully")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 036 failed: {e}")
            raise


def rollback_migration():
    """Rollback migration 036"""
    with SessionLocal() as session:
        try:
            logger.info("🔄 Rolling back Migration 036")
            session.execute(
                text(
                    """
                    ALTER TABLE streamers
                    DROP COLUMN IF EXISTS description
                    """
                )
            )
            session.commit()
            logger.info("✅ Migration 036 rollback completed")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 036 rollback failed: {e}")
            raise
