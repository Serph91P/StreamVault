"""
Migration 019: Create Share Tokens Table

Creates table for secure video share tokens with expiration.
"""

import logging
from sqlalchemy import text
from app.database import get_db

logger = logging.getLogger("streamvault")


def upgrade():
    """Create share tokens table"""
    db = next(get_db())
    try:
        logger.info("Migration 019: Creating share tokens table")

        # Create share_tokens table
        db.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS share_tokens (
                id SERIAL PRIMARY KEY,
                token VARCHAR(255) UNIQUE NOT NULL,
                stream_id INTEGER NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """
            )
        )

        # Create indexes for performance
        db.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_share_tokens_token
            ON share_tokens(token);
        """
            )
        )

        db.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_share_tokens_expires
            ON share_tokens(expires_at);
        """
            )
        )

        db.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_share_tokens_stream_id
            ON share_tokens(stream_id);
        """
            )
        )

        db.commit()
        logger.info("Migration 019 completed successfully")

    except Exception as e:
        logger.error(f"Migration 019 failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def downgrade():
    """Drop share tokens table"""
    db = next(get_db())
    try:
        logger.info("Migration 019 downgrade: Dropping share tokens table")

        db.execute(text("DROP TABLE IF EXISTS share_tokens;"))
        db.commit()

        logger.info("Migration 019 downgrade completed")

    except Exception as e:
        logger.error(f"Migration 019 downgrade failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    upgrade()
