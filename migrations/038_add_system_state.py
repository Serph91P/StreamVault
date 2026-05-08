"""
Migration 038: Add system_state singleton table

Persists global one-shot UI/onboarding flags so the welcome screen and
setup wizard no longer rely on browser localStorage. With localStorage the
welcome page reappeared on every new device, incognito session, or after
clearing cookies, even though setup had been completed long ago.

The table holds exactly one row (id = 1) and is upserted in-place.

Idempotent: safe to run multiple times.
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


def run_migration():
    """Create system_state table and seed the singleton row (PostgreSQL)."""

    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration 038: Add system_state")

            exists = session.execute(
                text("SELECT to_regclass('public.system_state') AS reg")
            ).fetchone()

            if exists and exists[0]:
                logger.info("✅ Table 'system_state' already exists, skipping create")
            else:
                session.execute(
                    text(
                        """
                        CREATE TABLE system_state (
                            id INTEGER PRIMARY KEY DEFAULT 1,
                            welcome_completed BOOLEAN NOT NULL DEFAULT FALSE,
                            welcome_completed_at TIMESTAMP WITH TIME ZONE,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                            CONSTRAINT system_state_singleton CHECK (id = 1)
                        )
                        """
                    )
                )
                logger.info("✅ Created 'system_state' table")

            # Seed singleton row if missing.
            session.execute(
                text(
                    """
                    INSERT INTO system_state (id, welcome_completed)
                    VALUES (1, FALSE)
                    ON CONFLICT (id) DO NOTHING
                    """
                )
            )

            session.commit()
            logger.info("✅ Migration 038 completed successfully")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 038 failed: {e}")
            raise


def rollback_migration():
    """Rollback migration 038"""
    with SessionLocal() as session:
        try:
            logger.info("🔄 Rolling back Migration 038")
            session.execute(text("DROP TABLE IF EXISTS system_state CASCADE"))
            session.commit()
            logger.info("✅ Migration 038 rollback completed")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 038 rollback failed: {e}")
            raise
