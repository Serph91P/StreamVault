# StreamVault Database Migrations

This directory contains database migration scripts for StreamVault.

## How Migrations Work

1. Migrations are automatically run when the application starts
2. Each migration script is run only once
3. Successful migrations are recorded in the database
4. New migrations are identified and applied on each restart

## Creating New Migrations

To create a new migration:

1. Create a new Python file in this directory (e.g., `migration_name.py`)
2. Implement a `run_migration()` function that performs the database changes
3. Handle errors appropriately in your migration
4. Test your migration locally before deploying

## Example Migration

```python
#!/usr/bin/env python
"""
Migration description
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

logger = logging.getLogger("streamvault")

def run_migration():
    """Migration implementation function"""
    try:
        # Connect to the database
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Perform database changes
        session.execute(text("ALTER TABLE my_table ADD COLUMN new_column INT"))
        session.commit()
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
```

## Migration Service

The migration service manages the process of:

1. Identifying which migrations need to be run
2. Running migrations in a consistent way
3. Recording successful migrations
4. Handling migration failures

You don't need to interact with the service directly. It runs automatically
when the application starts.
