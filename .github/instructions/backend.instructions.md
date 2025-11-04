---
applyTo: "app/**/*.py,migrations/**/*.py"
---

# Backend Development Guidelines

## 🔐 Security Requirements (MANDATORY)

**CRITICAL**: Read and follow `security.instructions.md` for comprehensive security guidelines.

### Path Security - Apply to ALL File Operations
```python
# ✅ ALWAYS: Validate user-provided paths
from app.utils.security import validate_path_security

def process_file(user_path: str):
    safe_path = validate_path_security(user_path, "read")
    with open(safe_path, 'r') as f:
        return f.read()

# ❌ NEVER: Direct file operations with user input
def process_file_unsafe(user_path: str):
    with open(user_path, 'r') as f:  # Path traversal vulnerability
        return f.read()
```

### Database Security - Prevent SQL Injection
```python
# ✅ ALWAYS: Use SQLAlchemy ORM
streams = db.query(Stream).filter(Stream.name == user_input).all()

# ✅ ALWAYS: Parameterized queries for raw SQL
result = db.execute(text("SELECT * FROM streams WHERE name = :name"), {"name": user_input})

# ❌ NEVER: String formatting with user input
query = f"SELECT * FROM streams WHERE name = '{user_input}'"  # SQL injection risk
```

### Input Validation - Required for ALL User Input
```python
# ✅ ALWAYS: Validate before processing
def create_stream(streamer_name: str, title: str):
    if not streamer_name or len(streamer_name.strip()) == 0:
        raise ValueError("Streamer name required")
    
    clean_name = validate_streamer_name(streamer_name)
    safe_title = html.escape(title.strip()[:200])
    
    # Now safe to use
    return Stream(streamer_name=clean_name, title=safe_title)
```

## Code Style

- Use type hints for all function parameters and return types
- Follow PEP 8 style guide
- Add docstrings for public APIs using Google style
- Never use bare `except:` - use specific exception types
- **NO MAGIC NUMBERS**: Extract all constants to module-level or configuration
- **DOCUMENT LOGIC CHANGES**: Add comments explaining why query filters changed
- **DOCUMENT BREAKING CHANGES**: Add `BREAKING CHANGE:` comments for behavior changes
- **SECURITY**: Validate ALL user input before processing
- **SECURITY**: Use parameterized queries, never string formatting

## Database & Performance

- Use `joinedload()` for relationships to avoid N+1 queries
- All database queries should use eager loading
- Use dependency injection for database sessions
- Add indexes for frequently queried columns

## Services Architecture

- Services in `app/services/` should be stateless where possible
- Use structured logging with context
- Implement proper error handling with specific exceptions
- Use TTLCache for caches that could grow unboundedly

## Configuration

- Put magic numbers in `app/config/constants.py`
- Use environment variables for secrets
- Validate configuration at startup

## Background Tasks

- Background tasks use queue system in `app/services/queues/`
- Implement graceful shutdown for long-running tasks
- Use WebSocket for real-time UI updates

## Testing

- Write unit tests for business logic
- Integration tests for API endpoints
- Use fixtures for database setup
- Mock external APIs (Twitch, Streamlink)

## Common Patterns

### Database Queries
```python
# ✅ CORRECT: Eager loading
streams = db.query(Stream).options(
    joinedload(Stream.streamer),
    joinedload(Stream.category)
).filter(Stream.ended_at.isnot(None)).all()

# ❌ WRONG: Lazy loading causes N+1
streams = db.query(Stream).all()
for stream in streams:
    print(stream.streamer.name)  # N+1 query
```

### Exception Handling
```python
# ✅ CORRECT: Specific exceptions
try:
    process.terminate()
except ProcessLookupError:
    logger.debug("Process already terminated")
except Exception as e:
    logger.error(f"Failed to terminate: {e}")

# ❌ WRONG: Bare except
try:
    process.terminate()
except:
    pass
```

### Logging
```python
# ✅ CORRECT: Structured logging
logger.info("Recording started", extra={
    "stream_id": stream.id,
    "streamer": stream.streamer.username
})

# ❌ WRONG: Unstructured
logger.info(f"Recording {stream.id} started")
```
