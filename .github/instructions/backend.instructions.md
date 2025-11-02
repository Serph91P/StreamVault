---
applyTo: "app/**/*.py,migrations/**/*.py"
---

# Backend Development Guidelines

## Code Style

- Use type hints for all function parameters and return types
- Follow PEP 8 style guide
- Add docstrings for public APIs using Google style
- Never use bare `except:` - use specific exception types

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
