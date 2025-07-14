# Graceful Shutdown Documentation

This document explains the graceful shutdown system implemented in StreamVault to ensure safe application termination.

## Overview

The graceful shutdown system ensures that:
1. **Active recordings are completed or safely terminated**
2. **Background tasks are properly cancelled**
3. **Database connections are closed cleanly**
4. **No data corruption occurs during shutdown**

## Shutdown Sequence

When StreamVault receives a shutdown signal (SIGTERM, SIGINT, or container stop), the following sequence occurs:

### 1. Recording Service Shutdown (30s timeout)
```
🛑 Starting graceful shutdown of Recording Service...
📛 Preventing new recordings from starting...
⏳ Waiting for X active recordings to complete...
🔄 Cancelling recording tasks...
🔄 Shutting down process manager...
🔄 Shutting down pipeline manager...
✅ Recording Service graceful shutdown completed
```

### 2. Background Tasks Cancellation
```
🔄 Cancelling cleanup task...
✅ cleanup task cancelled successfully
🔄 Cancelling log_cleanup task...
✅ log_cleanup task cancelled successfully
```

### 3. EventSub Cleanup
```
🔄 Stopping EventSub...
✅ EventSub stopped successfully
```

### 4. Database Cleanup
```
✅ Database connections closed
```

### 5. Completion
```
🎯 Application shutdown complete
```

## Components

### Recording Service Graceful Shutdown

The Recording Service implements comprehensive shutdown handling:

#### Key Features:
- **New Recording Prevention**: `_is_shutting_down` flag prevents new recordings
- **Active Recording Wait**: Waits up to 30 seconds for recordings to complete naturally
- **Force Termination**: Force stops remaining recordings after timeout
- **Task Cancellation**: Cancels all asyncio recording tasks
- **Component Shutdown**: Shuts down Process and Pipeline managers

#### Implementation:
```python
async def graceful_shutdown(self, timeout: int = 30):
    """Gracefully shutdown the recording service"""
    logger.info("🛑 Starting graceful shutdown of Recording Service...")
    self._is_shutting_down = True
    
    # Wait for active recordings to complete
    # Force stop remaining recordings
    # Cancel all recording tasks
    # Shutdown sub-managers
```

### Process Manager Graceful Shutdown

Handles termination of external recording processes:

#### Key Features:
- **Graceful Process Termination**: Sends SIGTERM first
- **Force Kill Fallback**: Uses SIGKILL if timeout exceeded
- **Segmented Process Handling**: Handles both regular and segmented recordings
- **Concurrent Termination**: Terminates multiple processes in parallel

#### Implementation:
```python
async def graceful_shutdown(self, timeout: int = 15):
    """Gracefully shutdown all recording processes"""
    # Terminate active processes with SIGTERM
    # Wait for graceful termination
    # Force kill if timeout exceeded
```

### Pipeline Manager Graceful Shutdown

Handles ongoing post-processing pipelines:

#### Key Features:
- **Natural Completion**: Waits for pipelines to complete naturally
- **Progress Monitoring**: Tracks remaining active pipelines
- **Timeout Handling**: Logs incomplete pipelines after timeout

#### Implementation:
```python
async def graceful_shutdown(self, timeout: int = 30):
    """Gracefully shutdown the pipeline manager"""
    # Wait for pipelines to complete
    # Log remaining pipelines after timeout
```

## Configuration

### Timeouts
```python
# Recording Service: 30 seconds
await recording_service.graceful_shutdown(timeout=30)

# Process Manager: 15 seconds per process
await process_manager.graceful_shutdown(timeout=15)

# Pipeline Manager: 30 seconds
await pipeline_manager.graceful_shutdown(timeout=30)
```

### Shutdown Prevention
During shutdown, new operations are prevented:
```python
# In recording service
if self._is_shutting_down:
    logger.warning("Cannot start recording: service is shutting down")
    return False
```

## Signal Handling

### Docker/Kubernetes
The application responds to standard container signals:
- **SIGTERM**: Graceful shutdown (preferred)
- **SIGINT**: Graceful shutdown (Ctrl+C)
- **SIGKILL**: Force kill (no cleanup possible)

### FastAPI Lifespan
The shutdown is managed through FastAPI's lifespan context manager:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    yield
    # Shutdown code - graceful shutdown happens here
```

## Monitoring Shutdown

### Log Messages
Watch for these log patterns during shutdown:
```bash
# Successful shutdown
🛑 Starting application shutdown...
✅ Recording service shutdown completed
✅ cleanup task cancelled successfully
✅ EventSub stopped successfully
✅ Database connections closed
🎯 Application shutdown complete

# Forced termination
⚠️ Force stopping 2 remaining recordings...
💀 Process for stream 123 force killed
```

### Troubleshooting

#### Recording Won't Stop
```bash
# Look for this pattern
⚠️ Force stopping X remaining recordings...
🛑 Force stopping recording for stream X
```
**Cause**: Recording process not responding to SIGTERM
**Action**: Check streamlink/ffmpeg process health

#### Long Shutdown Time
```bash
# Look for this pattern
⏳ Waiting for X active recordings to complete...
```
**Cause**: Recordings taking longer than expected
**Action**: Consider reducing timeout or checking stream health

#### Incomplete Pipelines
```bash
# Look for this pattern
⚠️ X pipelines still running after timeout
Pipeline still active: pipeline_123_456789
```
**Cause**: Post-processing taking longer than expected
**Action**: Check FFmpeg performance or file sizes

## Best Practices

### Development
```bash
# Graceful shutdown in development
docker-compose down        # Sends SIGTERM
docker-compose stop        # Sends SIGTERM with 10s timeout

# Force shutdown (avoid if possible)
docker-compose kill        # Sends SIGKILL
```

### Production
```bash
# Kubernetes graceful shutdown
kubectl delete pod streamvault-pod    # Sends SIGTERM, waits 30s, then SIGKILL

# Manual container shutdown
docker stop streamvault-container     # Sends SIGTERM, waits 10s, then SIGKILL
```

### Health Checks
Monitor these metrics during shutdown:
- **Active recordings count**: Should decrease to 0
- **Active processes count**: Should decrease to 0
- **Pipeline count**: Should decrease to 0
- **Database connections**: Should be closed

## Error Recovery

### Partial Shutdown Failure
If shutdown fails partially, the system will:
1. Log specific component failures
2. Continue with other shutdown steps
3. Close database connections as final step

### Recording Data Protection
During shutdown:
- **Completed recordings**: Fully preserved
- **Active recordings**: Partial files saved (may be incomplete)
- **Post-processing**: Completed where possible

### Manual Recovery
If shutdown fails completely:
```bash
# Check for orphaned processes
ps aux | grep streamlink
ps aux | grep ffmpeg

# Kill orphaned processes
kill -TERM <pid>  # Try graceful first
kill -KILL <pid>  # Force if needed

# Check for partial files
find /recordings -name "*.ts" -type f
find /recordings -name "*.tmp" -type f
```

## Performance Impact

### Shutdown Time
- **Typical shutdown**: 5-10 seconds
- **With active recordings**: 10-35 seconds
- **Maximum shutdown**: 45 seconds (with timeouts)

### Resource Cleanup
- **Memory**: All managers and tasks are properly cleaned up
- **File handles**: Database and file connections closed
- **Processes**: All child processes terminated
- **Network**: EventSub connections closed

The graceful shutdown system ensures StreamVault can be safely stopped without data loss or resource leaks.
