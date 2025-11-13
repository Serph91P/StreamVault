---
applyTo: "migrations/**/*.py"
---

# Database Migrations Guidelines

## 🚨 CRITICAL: StreamVault Uses Custom Migration System

**❌ DO NOT use Alembic commands (`alembic upgrade`, `alembic revision`, etc.)**  
**✅ USE the built-in migration system - migrations run automatically on app startup**

---

## Migration System Overview

### How It Works

```
Application Startup
  └─> app/migrations_init.py::run_migrations()
       └─> MigrationService.run_pending_migrations()
            ├─> Find all .py files in migrations/
            ├─> Check migrations table for already applied
            ├─> Run pending migrations in order
            └─> Record successful migrations in database
```

**Key Points:**
- ✅ Migrations run **automatically** on application startup
- ✅ Each migration runs **only once** (tracked in `migrations` table)
- ✅ Migrations run in **alphabetical order** by filename
- ✅ No manual intervention needed in production
- ❌ **NEVER** manually run migrations with Alembic
- ❌ **NEVER** execute migrations directly (no `python migrations/024_*.py`)

---

## Creating New Migrations

### Naming Convention

**Format:** `NNN_descriptive_name.py`

**Rules:**
- Use **3-digit zero-padded numbers** (e.g., `024`, `025`, `026`)
- Next available number (check `migrations/` folder for latest)
- Use **snake_case** for description
- Be descriptive but concise

**Examples:**
```
✅ 024_add_codec_preferences.py
✅ 025_create_proxy_health_table.py
✅ 026_add_notification_settings.py

❌ migration_024.py                    # Wrong format
❌ 24_add_codec.py                     # Not zero-padded
❌ add_codec_preferences.py            # Missing number
❌ 024_AddCodecPreferences.py          # Wrong case
```

---

## Migration File Template

```python
#!/usr/bin/env python
"""
Migration NNN: Descriptive Title

Brief explanation of what this migration does and why.

Changes:
- Add column X to table Y
- Create index on Z
- Update default values for existing rows
"""
import logging
from sqlalchemy import text, Column, String, Boolean, Integer
from app.database import SessionLocal
from app.config.settings import get_settings

logger = logging.getLogger("streamvault")

def run_migration():
    """
    Main migration function - REQUIRED name
    
    This function is called by MigrationService.
    Must handle all errors gracefully.
    """
    settings = get_settings()
    
    with SessionLocal() as session:
        try:
            logger.info("🔄 Running Migration NNN: Descriptive Title")
            
            # === STEP 1: Check if migration needed ===
            # Check if changes already exist (idempotency)
            check_result = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'your_table' 
                AND column_name = 'new_column'
            """)).fetchone()
            
            if check_result:
                logger.info("Migration NNN already applied (column exists), skipping")
                return
            
            # === STEP 2: Perform schema changes ===
            logger.info("Adding new column to your_table...")
            session.execute(text("""
                ALTER TABLE your_table 
                ADD COLUMN new_column VARCHAR(255) DEFAULT 'default_value'
            """))
            
            # === STEP 3: Create indexes (if needed) ===
            logger.info("Creating index on new_column...")
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_your_table_new_column 
                ON your_table(new_column)
            """))
            
            # === STEP 4: Update existing data (if needed) ===
            logger.info("Updating existing rows...")
            session.execute(text("""
                UPDATE your_table 
                SET new_column = 'updated_value' 
                WHERE new_column IS NULL
            """))
            
            # === STEP 5: Commit changes ===
            session.commit()
            logger.info("✅ Migration NNN completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Migration NNN failed: {e}")
            session.rollback()
            raise  # Re-raise to mark migration as failed


# For standalone testing (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
```

---

## Migration Patterns

### Pattern 1: Add Column with Default Value

```python
def run_migration():
    with SessionLocal() as session:
        try:
            # Check if column exists (idempotency)
            check = session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'recording_settings' 
                AND column_name = 'supported_codecs'
            """)).fetchone()
            
            if check:
                logger.info("Column already exists, skipping")
                return
            
            # Add column with default
            session.execute(text("""
                ALTER TABLE recording_settings 
                ADD COLUMN supported_codecs VARCHAR(100) 
                DEFAULT 'h264,h265' 
                NOT NULL
            """))
            
            session.commit()
            logger.info("✅ Added supported_codecs column")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise
```

### Pattern 2: Create New Table

```python
def run_migration():
    with SessionLocal() as session:
        try:
            # Check if table exists (idempotency)
            check = session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'proxy_health'
            """)).fetchone()
            
            if check:
                logger.info("Table already exists, skipping")
                return
            
            # Create table
            session.execute(text("""
                CREATE TABLE proxy_health (
                    id SERIAL PRIMARY KEY,
                    proxy_url VARCHAR(500) NOT NULL UNIQUE,
                    is_healthy BOOLEAN DEFAULT TRUE,
                    last_check TIMESTAMP DEFAULT NOW(),
                    response_time_ms INTEGER,
                    failure_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            
            # Create indexes
            session.execute(text("""
                CREATE INDEX idx_proxy_health_is_healthy 
                ON proxy_health(is_healthy)
            """))
            
            session.commit()
            logger.info("✅ Created proxy_health table")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise
```

### Pattern 3: Update Existing Data

```python
def run_migration():
    with SessionLocal() as session:
        try:
            # Get count of rows to update
            count_result = session.execute(text("""
                SELECT COUNT(*) FROM streamers 
                WHERE profile_image_url IS NULL
            """)).scalar()
            
            logger.info(f"Updating {count_result} streamers with default profile images")
            
            # Update in batches (for large tables)
            batch_size = 1000
            offset = 0
            
            while True:
                result = session.execute(text("""
                    UPDATE streamers 
                    SET profile_image_url = 'https://default.example.com/avatar.png'
                    WHERE id IN (
                        SELECT id FROM streamers 
                        WHERE profile_image_url IS NULL 
                        LIMIT :batch_size OFFSET :offset
                    )
                """), {"batch_size": batch_size, "offset": offset})
                
                if result.rowcount == 0:
                    break
                
                session.commit()
                offset += batch_size
                logger.info(f"Updated {offset} rows...")
            
            logger.info("✅ Updated all streamers")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise
```

### Pattern 4: Add Foreign Key Constraint

```python
def run_migration():
    with SessionLocal() as session:
        try:
            # Check if constraint exists (idempotency)
            check = session.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'recordings' 
                AND constraint_name = 'fk_recordings_streamer'
            """)).fetchone()
            
            if check:
                logger.info("Constraint already exists, skipping")
                return
            
            # Add foreign key
            session.execute(text("""
                ALTER TABLE recordings 
                ADD CONSTRAINT fk_recordings_streamer 
                FOREIGN KEY (streamer_id) 
                REFERENCES streamers(id) 
                ON DELETE CASCADE
            """))
            
            session.commit()
            logger.info("✅ Added foreign key constraint")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            session.rollback()
            raise
```

---

## Migration Best Practices

### 1. Always Check Idempotency

**Why:** Migrations may be run multiple times (restarts, rollbacks, manual testing)

```python
# ✅ ALWAYS: Check if changes already exist
check = session.execute(text("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'your_table' 
    AND column_name = 'new_column'
""")).fetchone()

if check:
    logger.info("Migration already applied, skipping")
    return

# ❌ NEVER: Assume migration hasn't run before
session.execute(text("ALTER TABLE your_table ADD COLUMN new_column VARCHAR(255)"))
# This will fail if column already exists!
```

### 2. Use Explicit Transaction Management

```python
# ✅ ALWAYS: Use context manager + explicit commit
with SessionLocal() as session:
    try:
        session.execute(text("..."))
        session.commit()  # Explicit commit
    except Exception as e:
        session.rollback()  # Explicit rollback
        raise

# ❌ NEVER: Rely on implicit commits
session.execute(text("..."))
# No commit = changes lost!
```

### 3. Log Progress for Long Migrations

```python
# ✅ ALWAYS: Log steps and progress
logger.info("🔄 Running Migration 025: Add Codec Support")
logger.info("Step 1/3: Adding columns...")
session.execute(text("..."))
logger.info("Step 2/3: Creating indexes...")
session.execute(text("..."))
logger.info("Step 3/3: Updating defaults...")
session.execute(text("..."))
logger.info("✅ Migration 025 completed successfully")

# ❌ NEVER: Silent migrations
session.execute(text("..."))  # No logging
session.execute(text("..."))
```

### 4. Handle Errors Gracefully

```python
# ✅ ALWAYS: Catch, log, rollback, and re-raise
try:
    session.execute(text("..."))
    session.commit()
except Exception as e:
    logger.error(f"❌ Migration failed: {e}")
    session.rollback()
    raise  # Re-raise so MigrationService marks as failed

# ❌ NEVER: Swallow errors
try:
    session.execute(text("..."))
except Exception:
    pass  # Silent failure - migration will be marked as success!
```

### 5. Use Parameterized Queries

```python
# ✅ ALWAYS: Use parameterized queries for safety
session.execute(text("""
    UPDATE streamers 
    SET default_quality = :quality 
    WHERE id = :id
"""), {"quality": "1080p60", "id": 123})

# ❌ NEVER: String formatting (SQL injection risk)
quality = "1080p60"
session.execute(text(f"UPDATE streamers SET default_quality = '{quality}'"))
```

### 6. Add Default Values for NOT NULL Columns

```python
# ✅ ALWAYS: Provide default for NOT NULL columns
session.execute(text("""
    ALTER TABLE recording_settings 
    ADD COLUMN supported_codecs VARCHAR(100) 
    DEFAULT 'h264,h265' 
    NOT NULL
"""))

# ❌ NEVER: Add NOT NULL without default (fails for existing rows)
session.execute(text("""
    ALTER TABLE recording_settings 
    ADD COLUMN supported_codecs VARCHAR(100) NOT NULL
"""))
# Error: Column "supported_codecs" contains null values
```

### 7. Create Indexes AFTER Bulk Data Changes

```python
# ✅ ALWAYS: Insert data first, then create index
session.execute(text("INSERT INTO large_table ..."))
session.commit()
session.execute(text("CREATE INDEX idx_large_table_column ON large_table(column)"))

# ❌ NEVER: Create index before bulk inserts (very slow)
session.execute(text("CREATE INDEX ..."))
session.execute(text("INSERT INTO large_table ..."))  # Slows down each insert
```

---

## Testing Migrations

### Local Testing

```bash
# 1. Start application (migrations run automatically)
python run_local.py

# 2. Check migration status
cd migrations
python manage.py list

# 3. Check logs
# Look for: "✅ Successfully applied migration: 025_your_migration.py"
```

### Manual Testing

```bash
# Run specific migration manually (for testing only)
cd migrations
python manage.py run 025_your_migration.py

# Force re-run (for testing changes)
python manage.py run 025_your_migration.py --force

# Mark as unapplied (to test again)
python manage.py mark 025_your_migration.py --status unapplied
```

---

## Common Migration Mistakes

### ❌ Mistake 1: Using Alembic Commands

```bash
# ❌ WRONG: StreamVault doesn't use Alembic
alembic upgrade head
alembic revision --autogenerate -m "Add column"

# ✅ CORRECT: Migrations run automatically on startup
python run_local.py  # That's it!
```

### ❌ Mistake 2: Running Migrations Directly

```bash
# ❌ WRONG: Don't execute migration files directly
python migrations/025_add_codec_support.py

# ✅ CORRECT: Let MigrationService handle it
python run_local.py  # Runs all pending migrations
```

### ❌ Mistake 3: Not Checking Idempotency

```python
# ❌ WRONG: Assumes migration never ran before
def run_migration():
    session.execute(text("ALTER TABLE streamers ADD COLUMN new_col VARCHAR(255)"))
    # Fails on second run: "column already exists"

# ✅ CORRECT: Check if changes already exist
def run_migration():
    check = session.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'streamers' 
        AND column_name = 'new_col'
    """)).fetchone()
    
    if check:
        logger.info("Column already exists, skipping")
        return
    
    session.execute(text("ALTER TABLE streamers ADD COLUMN new_col VARCHAR(255)"))
```

### ❌ Mistake 4: Missing Function Name

```python
# ❌ WRONG: Function named incorrectly
def do_migration():  # Wrong name!
    session.execute(text("..."))

# MigrationService won't find this function!

# ✅ CORRECT: Function must be named run_migration()
def run_migration():  # Correct name
    session.execute(text("..."))
```

---

## Checklist for New Migrations

**Before Creating:**
- [ ] Checked latest migration number in `migrations/` folder
- [ ] Planned database changes (columns, tables, indexes)
- [ ] Considered impact on existing data

**While Creating:**
- [ ] Named file with correct format: `NNN_description.py`
- [ ] Added docstring explaining purpose
- [ ] Implemented `run_migration()` function (exact name!)
- [ ] Added idempotency checks
- [ ] Used parameterized queries
- [ ] Added explicit error handling (try/except/raise)
- [ ] Used explicit transaction management (commit/rollback)
- [ ] Added progress logging

**After Creating:**
- [ ] Tested locally: `python run_local.py`
- [ ] Verified in logs: "✅ Successfully applied migration"
- [ ] Checked migration status: `python manage.py list`
- [ ] Verified database changes
- [ ] Committed migration file to git

---

## Related Documentation

- **Backend Guidelines:** `.github/instructions/backend.instructions.md`
- **Security Guidelines:** `.github/instructions/security.instructions.md`
- **Migration Service:** `app/services/system/migration_service.py`
- **Startup Script:** `app/migrations_init.py`

---

**Remember:**
- ✅ Migrations run **automatically on startup**
- ✅ Function must be named **`run_migration()`**
- ✅ Always check **idempotency**
- ✅ Use **explicit transactions**
- ❌ **NEVER use Alembic**
- ❌ **NEVER run migrations directly**

        """))
```

### Creating Indexes
```python
def up():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE INDEX idx_streams_ended_at 
            ON streams(ended_at) 
            WHERE ended_at IS NOT NULL
        """))
```

### Adding Constraints
```python
def up():
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE streams 
            ADD CONSTRAINT fk_streams_streamer 
            FOREIGN KEY (streamer_id) 
            REFERENCES streamers(id) 
            ON DELETE CASCADE
        """))
```

## Migration Testing

Before committing:
1. Test `up()` on fresh database
2. Test `down()` to verify rollback
3. Test `up()` again to ensure idempotency
4. Check query performance with `EXPLAIN ANALYZE`
