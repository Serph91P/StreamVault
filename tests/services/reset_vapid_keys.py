#!/usr/bin/env python3
"""
Script to reset VAPID keys in the database.
Run this if you're having issues with push notifications after upgrading.
"""

import os
import sys
import logging

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

from app.database import get_db
from app.models import SystemConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_vapid_keys():
    """Delete existing VAPID keys from database so new ones can be generated"""
    try:
        db = next(get_db())

        # Delete existing VAPID keys
        vapid_keys = ["VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_CLAIMS_SUB"]

        for key_name in vapid_keys:
            config = db.query(SystemConfig).filter(SystemConfig.key == key_name).first()
            if config:
                db.delete(config)
                logger.info(f"Deleted existing {key_name}")
            else:
                logger.info(f"No existing {key_name} found")

        db.commit()
        logger.info("✅ VAPID keys reset successfully")
        logger.info("🔄 Restart the application to generate new keys")

    except Exception as e:
        logger.error(f"❌ Failed to reset VAPID keys: {e}")
        if db:
            db.rollback()
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    reset_vapid_keys()
