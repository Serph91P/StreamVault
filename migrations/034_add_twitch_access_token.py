"""
Migration 034: Add Twitch Access Token Storage

Adds column to store the current access token in database (encrypted).

Problem:
- Access token was stored in settings.TWITCH_OAUTH_TOKEN (environment variable)
- Environment variables are not persistent across requests
- Token refresh updates settings but next request sees empty environment value
- Result: get_valid_access_token() always returns None

Solution:
- Store access token in database (encrypted like refresh token)
- Read from database instead of environment variable
- Token persists across requests and app restarts

Changes:
- Add twitch_access_token column (encrypted, nullable)
- Update TwitchTokenService to read/write from database

Security:
- Access tokens stored encrypted (same as refresh tokens)
- Tokens never logged or exposed in UI
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


from sqlalchemy.engine import Engine
from app.services.system.migration_service import migration_session


def run_migration(target_engine: Engine | None = None):
    """
    Add Twitch OAuth access token column to global_settings.

    This fixes the issue where access tokens are not persistent across requests
    because they were only stored in the environment variable.
    """

    with migration_session(target_engine, SessionLocal) as session:
        try:
            logger.info("🔄 Running Migration 034: Add Twitch Access Token")

            # === STEP 1: Check if column already exists (idempotency) ===
            check_result = session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'global_settings'
                AND column_name = 'twitch_access_token'
            """
                )
            )

            if check_result.fetchone():
                logger.info(
                    "✅ Migration 034: Column 'twitch_access_token' already exists - skipping"
                )
                return

            # === STEP 2: Add twitch_access_token column ===
            logger.info("📝 Adding 'twitch_access_token' column to global_settings...")

            session.execute(
                text(
                    """
                ALTER TABLE global_settings
                ADD COLUMN twitch_access_token TEXT NULL
            """
                )
            )

            session.commit()
            logger.info(
                "✅ Migration 034: Successfully added twitch_access_token column"
            )

            logger.info("💡 Access tokens will now persist across requests")
            logger.info(
                "💡 Token refresh will update database instead of environment variable"
            )

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 034 failed: {e}")
            raise


def rollback_migration():
    """
    Rollback migration 034 by removing twitch_access_token column.

    WARNING: This will clear any stored access tokens.
    """
    with SessionLocal() as session:
        try:
            logger.info("🔄 Rolling back Migration 034: Remove Twitch Access Token")

            session.execute(
                text(
                    """
                ALTER TABLE global_settings
                DROP COLUMN IF EXISTS twitch_access_token
            """
                )
            )

            session.commit()
            logger.info("✅ Migration 034 rollback complete")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 034 rollback failed: {e}")
            raise


if __name__ == "__main__":
    # Allow running migration directly for testing
    run_migration()
