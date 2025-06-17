"""
Migration: Add proxy settings to GlobalSettings

This migration adds HTTP and HTTPS proxy configuration fields
to the global_settings table for Streamlink proxy support.
"""

from sqlalchemy import text
import logging

logger = logging.getLogger('streamvault.migration')

def upgrade(connection):
    """Add proxy settings columns to global_settings table"""
    try:
        # Add http_proxy column
        connection.execute(text("""
            ALTER TABLE global_settings 
            ADD COLUMN http_proxy VARCHAR(255)
        """))
        logger.info("Added http_proxy column to global_settings")
        
        # Add https_proxy column  
        connection.execute(text("""
            ALTER TABLE global_settings 
            ADD COLUMN https_proxy VARCHAR(255)
        """))
        logger.info("Added https_proxy column to global_settings")
        
        connection.commit()
        logger.info("Successfully added proxy settings to global_settings table")
        
    except Exception as e:
        logger.error(f"Error adding proxy settings columns: {e}")
        connection.rollback()
        raise

def downgrade(connection):
    """Remove proxy settings columns from global_settings table"""
    try:
        # Remove https_proxy column
        connection.execute(text("""
            ALTER TABLE global_settings 
            DROP COLUMN https_proxy
        """))
        logger.info("Removed https_proxy column from global_settings")
        
        # Remove http_proxy column
        connection.execute(text("""
            ALTER TABLE global_settings 
            DROP COLUMN http_proxy
        """))
        logger.info("Removed http_proxy column from global_settings")
        
        connection.commit()
        logger.info("Successfully removed proxy settings from global_settings table")
        
    except Exception as e:
        logger.error(f"Error removing proxy settings columns: {e}")
        connection.rollback()
        raise

if __name__ == "__main__":
    print("This migration adds HTTP/HTTPS proxy support to StreamVault")
    print("Fields added:")
    print("- global_settings.http_proxy")
    print("- global_settings.https_proxy")
