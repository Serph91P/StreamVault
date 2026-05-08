"""
Migration 037: Add API Keys table

Creates the `api_keys` table that stores long-lived programmatic access tokens.
The raw key is shown to the user exactly once at creation; only a SHA-256 hash
is persisted. API keys allow external monitoring tooling to call StreamVault
endpoints (e.g. /api/status/recordings-active) without an interactive login.

Idempotent: safe to run multiple times.
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


def run_migration():
    """Create api_keys table (PostgreSQL)."""

    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration 037: Add API Keys")

            exists = session.execute(
                text(
                    """
                    SELECT to_regclass('public.api_keys') AS reg
                    """
                )
            ).fetchone()

            if exists and exists[0]:
                logger.info("✅ Table 'api_keys' already exists, skipping create")
            else:
                session.execute(
                    text(
                        """
                        CREATE TABLE api_keys (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            name VARCHAR NOT NULL,
                            key_hash VARCHAR NOT NULL UNIQUE,
                            key_prefix VARCHAR(12) NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
                            last_used_at TIMESTAMP WITH TIME ZONE,
                            revoked_at TIMESTAMP WITH TIME ZONE
                        )
                        """
                    )
                )
                session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id)"
                    )
                )
                session.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_api_keys_key_hash ON api_keys (key_hash)"
                    )
                )
                logger.info("✅ Created 'api_keys' table")

            session.commit()
            logger.info("✅ Migration 037 completed successfully")

        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 037 failed: {e}")
            raise


def rollback_migration():
    """Rollback migration 037"""
    with SessionLocal() as session:
        try:
            logger.info("🔄 Rolling back Migration 037")
            session.execute(text("DROP TABLE IF EXISTS api_keys CASCADE"))
            session.commit()
            logger.info("✅ Migration 037 rollback completed")
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Migration 037 rollback failed: {e}")
            raise
