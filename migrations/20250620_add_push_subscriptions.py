#!/usr/bin/env python
"""
Migration: Add push subscription table

This migration creates the push_subscriptions table for managing
push notification subscriptions for PWA functionality.
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """
    Creates the push_subscriptions table for PWA push notifications
    """
    try:
        # Connect to the database
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Create push_subscriptions table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id SERIAL PRIMARY KEY,
            endpoint VARCHAR UNIQUE NOT NULL,
            subscription_data TEXT NOT NULL,
            user_agent VARCHAR,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        session.execute(text(create_table_sql))
        logger.info("Created push_subscriptions table")
        
        # Create indexes for better performance
        index_endpoint_sql = """
        CREATE INDEX IF NOT EXISTS ix_push_subscriptions_endpoint 
        ON push_subscriptions (endpoint);
        """
        
        index_active_sql = """
        CREATE INDEX IF NOT EXISTS ix_push_subscriptions_is_active 
        ON push_subscriptions (is_active);
        """
        
        session.execute(text(index_endpoint_sql))
        logger.info("Created index on endpoint column")
        
        session.execute(text(index_active_sql))
        logger.info("Created index on is_active column")
        
        # Add updated_at trigger for automatic timestamp updates
        trigger_sql = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_push_subscriptions_updated_at ON push_subscriptions;
        
        CREATE TRIGGER update_push_subscriptions_updated_at
            BEFORE UPDATE ON push_subscriptions
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
        
        session.execute(text(trigger_sql))
        logger.info("Created updated_at trigger")
        
        session.commit()
        logger.info("Push subscriptions migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
