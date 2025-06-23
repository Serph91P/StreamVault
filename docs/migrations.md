# Database Migrations Guide

## Overview

StreamVault uses a robust database migration system that ensures all database schema changes are applied safely and consistently across different environments.

## Migration System Features

### ✅ Idempotent Migrations
- All migrations can be run multiple times safely
- Existing tables and columns are detected and skipped
- No risk of duplicate schema changes

### 🔄 Automatic Execution
- Migrations run automatically on application startup
- Manual execution options available for troubleshooting
- Comprehensive error handling and logging

### 📊 Migration Tracking
- All migrations are tracked in the `applied_migrations` table
- Status tracking (success/failure) for each migration
- Detailed timestamps and execution history

## Migration Files

### Current Migrations

1. **20250522_add_stream_indices.py**
   - Adds database indices for better query performance
   - Indices on: streamer_id, started_at, title

2. **20250609160908_add_recording_path_to_streams.py**
   - Adds `recording_path` column to streams table
   - Stores the filesystem path for each recording

3. **20250617_add_proxy_settings.py**
   - Adds HTTP/HTTPS proxy configuration to global_settings
   - Columns: http_proxy, https_proxy

4. **20250620_add_push_subscriptions.py**
   - Creates push_subscriptions table for PWA notifications
   - Includes endpoint, subscription_data, and management fields

5. **20250620_add_system_config.py**
   - Creates system_config table for persistent configuration
   - Used for VAPID keys and other system-wide settings

## Running Migrations

### Automatic (Recommended)
Migrations run automatically when the application starts. No manual intervention required.

### Manual Execution

#### Using Shell Scripts
```bash
# Linux/macOS
./migrate.sh

# Windows PowerShell
.\migrate.ps1
```

#### Using Python Directly
```bash
# Run safe migrations via MigrationService
python -c "from app.services.migration_service import MigrationService; MigrationService.run_safe_migrations()"

# Validate database schema
python validate_database.py
```

## Migration Logs

### Successful Migration Log
```
🚀 Starting safe migration process...
✅ Migrations tracking table ready
⏭️  Migration 20250522_add_stream_indices already applied, skipping
🔄 Running migration: Add recording_path column to streams table
✅ Migration 20250609_add_recording_path completed successfully
🎯 Migration summary: 4 successful, 0 failed
```

### Handling Migration Errors

Common migration errors and their meanings:

#### "Column already exists"
```
ERROR: column "recording_path" of relation "streams" already exists
```
- **Cause**: Migration was already applied
- **Solution**: This is expected behavior with idempotent migrations
- **Action**: No action required - migration will be skipped

#### "Table already exists"
```
ERROR: relation "push_subscriptions" already exists
```
- **Cause**: Table was already created
- **Solution**: Migration uses `CREATE TABLE IF NOT EXISTS`
- **Action**: No action required

## Database Schema Validation

Use the validation script to check your database schema:

```bash
python validate_database.py
```

### Validation Output
```
🔍 Validating database schema...
✅ Table 'streamers' exists
✅ Table 'streams' exists
✅ Column 'streams.recording_path' exists
✅ Index 'idx_streams_streamer_id' exists
📊 5 migrations tracked in database
🎉 Database schema validation passed!
```

## Troubleshooting

### Migration Failures

1. **Check Database Connection**
   ```bash
   # Verify database is accessible
   python -c "from app.database import engine; print(engine.connect())"
   ```

2. **Check Migration Logs**
   - Look for specific error messages in application logs
   - Check `applied_migrations` table for failure records

3. **Manual Recovery**
   ```sql
   -- Check migration status
   SELECT * FROM applied_migrations ORDER BY applied_at DESC;
   
   -- Mark failed migration as success (if manually fixed)
   UPDATE applied_migrations 
   SET success = true 
   WHERE migration_name = 'problem_migration_name';
   ```

### Performance Issues

If migrations take too long:

1. **Check Database Load**
   - Ensure database isn't under heavy load
   - Consider running migrations during maintenance windows

2. **Index Creation**
   - Large tables may take time to index
   - Index creation is normal for production databases

## Best Practices

### Development
- Always test migrations on development environment first
- Use the validation script after adding new migrations
- Monitor migration logs during development

### Production
- Backup database before major migrations
- Monitor application logs during startup
- Validate schema after deployment

### Creating New Migrations

When creating new migrations:

1. **Use Idempotent SQL**
   ```sql
   -- Good: Uses IF NOT EXISTS
   CREATE TABLE IF NOT EXISTS new_table (...);
   
   -- Good: Check before adding column
   ALTER TABLE existing_table 
   ADD COLUMN IF NOT EXISTS new_column VARCHAR(255);
   ```

2. **Test Thoroughly**
   - Test on fresh database
   - Test on existing database with data
   - Test running migration multiple times

3. **Document Changes**
   - Update this guide with new migrations
   - Include migration purpose and impact
   - Document any manual steps required

## Migration System Architecture

```
MigrationService (app/services/migration_service.py)
├── ensure_migrations_table()         # Create tracking table
├── is_migration_applied()            # Check if migration ran
├── mark_migration_applied()          # Record migration status
├── run_safe_migrations()             # Execute all migrations safely
│   ├── _run_indices_migration()
│   ├── _run_recording_path_migration()
│   ├── _run_proxy_settings_migration()
│   ├── _run_push_subscriptions_migration()
│   └── _run_system_config_migration()
└── Legacy methods (for backward compatibility)
    ├── get_all_migration_scripts()
    ├── run_migration_script()
    └── run_all_migrations()
```

## Legacy Migration System

The old migration system is still available as a fallback:

```python
# Legacy system (still available for complex migrations)
from app.services.migration_service import MigrationService
MigrationService.run_all_migrations()  # Runs migration files from migrations/ directory
```

The new safe migration system is preferred and runs automatically. The legacy system is used as a fallback if the safe system encounters issues.

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
