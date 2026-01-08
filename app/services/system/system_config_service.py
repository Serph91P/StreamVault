"""
Service for managing persistent system configuration
"""

import logging
from typing import Optional, Dict
from app.models import SystemConfig
from app.database import SessionLocal

logger = logging.getLogger("streamvault")


class SystemConfigService:
    """Service for managing system-wide configuration settings"""

    @staticmethod
    def get_config(key: str) -> Optional[str]:
        """Get a configuration value by key"""
        try:
            session = SessionLocal()
            try:
                config = session.query(SystemConfig).filter(SystemConfig.key == key).first()
                return config.value if config else None
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Failed to get config {key}: {e}")
            return None

    @staticmethod
    def set_config(key: str, value: str, description: Optional[str] = None) -> bool:
        """Set a configuration value"""
        try:
            session = SessionLocal()
            try:
                config = session.query(SystemConfig).filter(SystemConfig.key == key).first()

                if config:
                    # Update existing
                    config.value = value
                    if description:
                        config.description = description
                else:
                    # Create new
                    config = SystemConfig(key=key, value=value, description=description)
                    session.add(config)

                session.commit()
                return True
            finally:
                session.close()

        except Exception as e:
            logger.error(f"Failed to set config {key}: {e}")
            return False

    @staticmethod
    def get_vapid_keys() -> Dict[str, Optional[str]]:
        """Get VAPID keys from database"""
        return {
            "public_key": SystemConfigService.get_config("vapid_public_key"),
            "private_key": SystemConfigService.get_config("vapid_private_key"),
            "claims_sub": SystemConfigService.get_config("vapid_claims_sub"),
        }

    @staticmethod
    def set_vapid_keys(public_key: str, private_key: str, claims_sub: str) -> bool:
        """Store VAPID keys in database"""
        try:
            success = True
            success &= SystemConfigService.set_config(
                "vapid_public_key", public_key, "VAPID public key for push notifications"
            )
            success &= SystemConfigService.set_config(
                "vapid_private_key", private_key, "VAPID private key for push notifications"
            )
            success &= SystemConfigService.set_config(
                "vapid_claims_sub", claims_sub, "VAPID claims subject for push notifications"
            )

            if success:
                logger.info("✅ VAPID keys stored in database successfully")
            else:
                logger.error("❌ Failed to store some VAPID keys")

            return success

        except Exception as e:
            logger.error(f"Failed to store VAPID keys: {e}")
            return False


# Global instance
system_config_service = SystemConfigService()
