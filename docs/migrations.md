# StreamVault Database Migration System

This document explains how to use and manage the automated database migration system in StreamVault.

## Overview

The StreamVault migration system automatically applies database schema changes whenever the application is started. This ensures that the database schema is always up-to-date without requiring manual intervention, which is especially important in Docker container environments.

## How It Works

1. When the application starts, it checks for any pending migrations
2. Each migration is run exactly once (successful migrations are tracked in the database)
3. New migrations are automatically detected and applied
4. Failed migrations are logged but don't prevent the application from starting

## Creating a New Migration

To create a new migration, use the provided helper script:

```bash
cd /home/maxe/Dokumente/privat_projects/StreamVault
python migrations/create_migration.py name_of_migration
```

This will:
1. Create a timestamped Python file based on the template
2. Name the file with the format: `YYYYMMDDHHMMSS_name_of_migration.py`
3. Set up all the necessary boilerplate code

## Writing Migration Code

After creating a migration file, edit it to implement your database changes:

1. Open the generated file in your preferred editor
2. Replace the placeholder comment with a description of what the migration does
3. Add your SQLAlchemy or raw SQL commands in the `run_migration()` function
4. Handle any potential errors

Example migration:

```python
def run_migration():
    """
    Add a new column to the streamers table
    """
    try:
        # Connect to the database
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if column exists before adding it
        inspector = engine.dialect.get_inspector(engine)
        columns = [c['name'] for c in inspector.get_columns('streamers')]
        
        if 'new_column' not in columns:
            logger.info("Adding new_column to streamers table")
            session.execute(text("ALTER TABLE streamers ADD COLUMN new_column TEXT"))
            session.commit()
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
```

## Testing a Migration

To test a migration before deploying:

1. Create a backup of your development database
2. Place the migration file in the migrations directory
3. Restart your development instance
4. Check the logs to confirm the migration ran successfully

## Deployment

The migration system works seamlessly with Docker:

1. When you add new migrations, they are copied to the container at build time
2. When the container starts, it automatically runs any pending migrations
3. The application then starts with the updated database schema

No additional steps are required for deployment - just build and run the container.

## Troubleshooting

### Failed Migrations

If a migration fails:

1. Review the error message in the logs
2. Fix the migration file
3. Restart the application to retry

### Manual Intervention

In certain cases, you may need to manually mark a migration as applied:

```sql
-- Execute this in your database:
INSERT INTO migrations (script_name, applied_at, success) 
VALUES ('migration_filename.py', NOW(), TRUE);
```

### Common Issues

- **Error: "Column already exists"**: Your migration tried to add a column that already exists
- **Error: "Table doesn't exist"**: Your migration tried to modify a table that doesn't exist
- **Error: "Permission denied"**: The database user doesn't have enough privileges

## Best Practices

1. **One change per migration**: Keep migrations focused on a single change
2. **Check before changing**: Always verify if a structure exists before modifying it
3. **Include rollback options**: Where possible, add comments with SQL to undo changes
4. **Test thoroughly**: Always test migrations in development before deploying
5. **Version control**: Keep migrations in version control with the rest of your code
