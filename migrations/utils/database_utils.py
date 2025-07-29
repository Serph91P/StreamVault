"""
Database utility functions for migrations
"""
import logging
from sqlalchemy import Engine

logger = logging.getLogger(__name__)

def get_database_type(engine: Engine) -> str:
    """
    Get the database type from SQLAlchemy engine
    
    Args:
        engine: SQLAlchemy engine instance
        
    Returns:
        str: Database dialect name (e.g., 'sqlite', 'postgresql', 'mysql')
    """
    database_type = engine.dialect.name
    logger.debug(f"Detected database type: {database_type}")
    return database_type

def is_sqlite(engine: Engine) -> bool:
    """Check if the database is SQLite"""
    return get_database_type(engine) == 'sqlite'

def is_postgresql(engine: Engine) -> bool:
    """Check if the database is PostgreSQL"""
    return get_database_type(engine) == 'postgresql'

def is_mysql(engine: Engine) -> bool:
    """Check if the database is MySQL"""
    return get_database_type(engine) == 'mysql'
