"""
Migration 032: Add proxy encryption key to GlobalSettings

Adds 'proxy_encryption_key' column to global_settings table to persist the
Fernet encryption key used for encrypting proxy credentials in the database.

This fixes the critical issue where the encryption key was generated at runtime
and not persisted, causing proxies to become unreadable after container restarts.

Security: The encryption key is now stored in the database (not in logs) and
persists across container rebuilds, ensuring existing proxies remain decryptable.

Changes:
- Add proxy_encryption_key column to global_settings table
- Auto-generates encryption key on first proxy operation
- No manual user intervention required
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


def run_migration():
    """
    Add proxy_encryption_key column to global_settings.

    This migration enables persistent storage of the Fernet encryption key,
    preventing data loss when containers restart.
    """

    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration 032: Add Proxy Encryption Key")

            # === STEP 1: Check if column already exists (idempotency) ===
            check_result = session.execute(
                text(
                    """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'global_settings'
                AND column_name = 'proxy_encryption_key'
            """
                )
            ).fetchone()

            if check_result:
                logger.info("Migration 032 already applied (column exists), skipping")
                return

            # === STEP 2: Add proxy_encryption_key column ===
            logger.info("Adding proxy_encryption_key column to global_settings...")
            session.execute(
                text(
                    """
                ALTER TABLE global_settings
                ADD COLUMN proxy_encryption_key VARCHAR(255) DEFAULT NULL
            """
                )
            )

            # === STEP 3: Commit changes ===
            session.commit()
            logger.info("✅ Migration 032 completed successfully")
            logger.info("💡 Proxy encryption key now persists across container restarts")
            logger.info("   - No manual copying from logs required")
            logger.info("   - Existing proxies remain decryptable after restart")

        except Exception as e:
            logger.error(f"❌ Migration 032 failed: {e}")
            session.rollback()
            raise


# For standalone testing (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
