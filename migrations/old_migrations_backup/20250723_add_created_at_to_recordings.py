#!/usr/bin/env python
"""
Migration: Add created_at field to recordings table
Date: 2025-07-23
Description: Adds a created_at timestamp field to the recordings table for tracking when recordings were created
"""
import logging
from sqlalchemy import text
from app.database import engine

logger = logging.getLogger("streamvault")

def upgrade():
    """
    Add created_at field to recordings table
    """
    with engine.connect() as connection:
        logger.info("🔄 Starting migration: Add created_at to recordings table")
        
        # Check if the column already exists
        check_column_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'recordings' AND column_name = 'created_at'
        """
        
        result = connection.execute(text(check_column_sql)).fetchone()
        
        if result:
            logger.info("Column 'created_at' already exists in recordings table, skipping migration")
            return
        
        # Add the created_at column with a default value
        alter_table_sql = """
        ALTER TABLE recordings 
        ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        """
        
        connection.execute(text(alter_table_sql))
        
        # Update existing records to have created_at = start_time (reasonable default)
        update_existing_sql = """
        UPDATE recordings 
        SET created_at = start_time 
        WHERE created_at IS NULL
        """
        
        connection.execute(text(update_existing_sql))
        
        # Make sure the default constraint is properly set for future records
        set_default_sql = """
        ALTER TABLE recordings 
        ALTER COLUMN created_at SET DEFAULT NOW()
        """
        
        connection.execute(text(set_default_sql))
        
        connection.commit()
        
        logger.info("✅ Migration completed successfully: created_at column added to recordings table")

def downgrade():
    """
    Remove created_at field from recordings table
    """
    with engine.connect() as connection:
        logger.info("🔄 Rolling back migration: Remove created_at from recordings table")
        
        # Check if the column exists before trying to drop it
        check_column_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'recordings' AND column_name = 'created_at'
        """
        
        result = connection.execute(text(check_column_sql)).fetchone()
        
        if not result:
            logger.info("Column 'created_at' does not exist in recordings table, skipping rollback")
            return
        
        # Drop the created_at column
        drop_column_sql = """
        ALTER TABLE recordings 
        DROP COLUMN created_at
        """
        
        connection.execute(text(drop_column_sql))
        connection.commit()
        
        logger.info("✅ Migration rollback completed: created_at column removed from recordings table")
