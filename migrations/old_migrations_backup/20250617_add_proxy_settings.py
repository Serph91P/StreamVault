#!/usr/bin/env python
"""
Migration: Add proxy settings to GlobalSettings

This migration adds HTTP and HTTPS proxy configuration fields
to the global_settings table for Streamlink proxy support.
"""

import logging
import sqlalchemy as sa
from alembic import op

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "20250617_add_proxy_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add proxy settings columns to global_settings table"""
    try:
        # Add http_proxy column
        op.add_column("global_settings", sa.Column("http_proxy", sa.String(255), nullable=True))
        logger.info("Added http_proxy column to global_settings")

        # Add https_proxy column
        op.add_column("global_settings", sa.Column("https_proxy", sa.String(255), nullable=True))
        logger.info("Added https_proxy column to global_settings")

        logger.info("Successfully added proxy settings to global_settings table")

    except Exception as e:
        logger.error(f"Error adding proxy settings columns: {e}")
        raise


def downgrade():
    """Remove proxy settings columns from global_settings table"""
    try:
        # Remove https_proxy column
        op.drop_column("global_settings", "https_proxy")
        logger.info("Removed https_proxy column from global_settings")

        # Remove http_proxy column
        op.drop_column("global_settings", "http_proxy")
        logger.info("Removed http_proxy column from global_settings")

        logger.info("Successfully removed proxy settings from global_settings table")

    except Exception as e:
        logger.error(f"Error removing proxy settings columns: {e}")
        raise


if __name__ == "__main__":
    print("This migration adds HTTP/HTTPS proxy support to StreamVault")
    print("Fields added:")
    print("- global_settings.http_proxy")
    print("- global_settings.https_proxy")
