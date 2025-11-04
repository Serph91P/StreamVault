---
applyTo: "migrations/**/*.py"
---

# Database Migration Guidelines

## Migration Structure

Each migration file must follow this pattern:

```python
"""
Migration: <number>_<description>
Description: <detailed description>
Author: <name>
Date: <YYYY-MM-DD>
"""

from sqlalchemy import text
from app.database import engine

def up():
    """Apply migration"""
    with engine.begin() as conn:
        # Migration logic here
        pass

def down():
    """Rollback migration"""
    with engine.begin() as conn:
        # Rollback logic here
        pass
```

## Best Practices

- **Always provide both `up()` and `down()` functions** for reversibility
- **Use transactions** - all changes should be atomic
- **Test migrations** on development database before production
- **Add indexes** for foreign keys and frequently queried columns
- **Use raw SQL** via `text()` for complex operations

## Naming Convention

Migrations are numbered sequentially:
- `001_create_base_tables.py`
- `002_create_main_entities.py`
- `003_add_indexes.py`

## Common Patterns

### Adding Columns
```python
def up():
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE streams 
            ADD COLUMN episode_number INTEGER DEFAULT 1
        """))

def down():
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE streams 
            DROP COLUMN episode_number
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
