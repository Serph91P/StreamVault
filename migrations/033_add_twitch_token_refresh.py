"""
Migration 033: Add Twitch OAuth Refresh Token Storage

Adds columns to global_settings to store Twitch OAuth refresh token and expiration
timestamp, enabling automatic token refresh without manual intervention.

Problem:
- Current: TWITCH_OAUTH_TOKEN must be manually copied from Twitch every 4-6 hours
- Access tokens expire, causing recordings to fail
- No way to automatically refresh tokens

Solution:
- Store refresh_token (long-lived, months/years validity)
- Store token_expires_at (timestamp when access token expires)
- Auto-refresh access token before it expires
- Works seamlessly with Twitch Turbo (ad-free streams)

Changes:
- Add twitch_refresh_token column (encrypted, nullable)
- Add twitch_token_expires_at column (timestamp, nullable)
- Enables automatic OAuth token management

Security:
- Refresh tokens stored encrypted (same as proxy passwords)
- Access tokens refreshed automatically before expiration
- No tokens logged or exposed in UI
"""

import logging
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


def run_migration():
    """
    Add Twitch OAuth refresh token and expiration columns to global_settings.
    
    This migration enables automatic token refresh, eliminating the need to
    manually update TWITCH_OAUTH_TOKEN every few hours.
    """
    
    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration 033: Add Twitch Token Refresh")
            
            # === STEP 1: Check if columns already exist (idempotency) ===
            check_result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'global_settings' 
                AND column_name IN ('twitch_refresh_token', 'twitch_token_expires_at')
            """)).fetchall()
            
            existing_columns = {row[0] for row in check_result}
            
            if 'twitch_refresh_token' in existing_columns and 'twitch_token_expires_at' in existing_columns:
                logger.info("Migration 033 already applied (columns exist), skipping")
                return
            
            # === STEP 2: Add twitch_refresh_token column (encrypted) ===
            if 'twitch_refresh_token' not in existing_columns:
                logger.info("Adding twitch_refresh_token column to global_settings...")
                session.execute(text("""
                    ALTER TABLE global_settings 
                    ADD COLUMN twitch_refresh_token TEXT DEFAULT NULL
                """))
                logger.info("✅ Added twitch_refresh_token column")
            
            # === STEP 3: Add twitch_token_expires_at column (timestamp) ===
            if 'twitch_token_expires_at' not in existing_columns:
                logger.info("Adding twitch_token_expires_at column to global_settings...")
                session.execute(text("""
                    ALTER TABLE global_settings 
                    ADD COLUMN twitch_token_expires_at TIMESTAMP DEFAULT NULL
                """))
                logger.info("✅ Added twitch_token_expires_at column")
            
            # === STEP 4: Commit changes ===
            session.commit()
            logger.info("✅ Migration 033 completed successfully")
            logger.info("💡 Twitch OAuth tokens now auto-refresh:")
            logger.info("   - No more manual token copying every 4-6 hours")
            logger.info("   - Refresh token stored securely (encrypted)")
            logger.info("   - Access token refreshed automatically before expiration")
            logger.info("   - Compatible with Twitch Turbo (ad-free streams)")
            
        except Exception as e:
            logger.error(f"❌ Migration 033 failed: {e}")
            session.rollback()
            raise


# For standalone testing (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
