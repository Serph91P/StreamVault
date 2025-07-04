# StreamVault Admin Test System

The StreamVault Admin Test System provides comprehensive testing for all critical application functions.

## Features

### System Health Check
- Quick verification of critical system components
- Database connection
- FFmpeg and Streamlink availability  
- Disk space
- Proxy configuration

### Comprehensive Test Suite
- **System Dependencies**: Verification of all required tools (streamlink, ffmpeg, ffprobe)
- **Infrastructure**: Database, file permissions, disk space
- **Core Functionality**: Recording workflow, metadata generation, media server structure
- **Communication**: Push notifications, WebSocket connections

### System Information
- Platform and system details
- CPU and memory usage
- Disk space overview
- Configuration status

### Maintenance Tools
- Temporary file cleanup
- Log viewer with filter options
- System status monitoring

## Usage

### Web Interface
Navigate to `/admin` in the StreamVault web application for the graphical interface.

### API Endpoints

#### Quick Health Check
```bash
POST /api/admin/tests/quick-health
```

#### Run All Tests
```bash
POST /api/admin/tests/run
```

#### Get System Info
```bash
GET /api/admin/system/info
```

#### Show Available Tests
```bash
GET /api/admin/tests/available
```

#### Clean Temporary Files
```bash
POST /api/admin/maintenance/cleanup-temp
```

#### View Logs
```bash
GET /api/admin/logs/recent?lines=100&level=INFO
```

## Test Categories

### System Tests
- `dependency_streamlink`: Streamlink installation and version
- `dependency_ffmpeg`: FFmpeg installation and version
- `dependency_ffprobe`: FFprobe installation and version
- `dependency_python`: Python installation and version

### Infrastructure Tests
- `database_connection`: Database connection and basic operations
- `file_permissions`: File system permissions in recording directory
- `disk_space`: Available disk space
- `proxy_connection`: Proxy connection (if configured)

### Core Functionality Tests
- `streamlink_functionality`: Streamlink with test stream
- `ffmpeg_functionality`: FFmpeg video processing
- `recording_workflow`: Complete recording workflow (TS→MP4)
- `metadata_generation`: Metadata file creation (JSON, NFO, chapters, etc.)
- `media_server_structure`: Media server folder structure

### Communication Tests
- `push_notifications`: Push notification system
- `websocket_functionality`: WebSocket connections

## Result Interpretation

### Status Codes
- ✅ **Healthy/Passed**: Everything works correctly
- ⚠️ **Warning**: Works but with limitations
- ❌ **Error/Failed**: Not working or critical error

### Critical Tests
These tests should always pass:
- `database_connection`
- `dependency_ffmpeg`
- `dependency_streamlink`
- `file_permissions`
- `disk_space` (at least 5GB free)

### Optional Tests
These tests can fail without affecting basic functionality:
- `proxy_connection` (only if proxy configured)
- `push_notifications` (only if VAPID keys configured)

## Troubleshooting

### FFmpeg Tests Failing
- Check FFmpeg installation: `ffmpeg -version`
- Ensure FFmpeg is in PATH

### Streamlink Tests Failing
- Check Streamlink installation: `streamlink --version`
- Test manual Streamlink connection

### Database Tests Failing
- Check database connection in settings
- Ensure database is running

### Disk Space Warnings
- Clean up old recordings
- Use integrated cleanup tool
- Expand storage capacity

### Permission Errors
- Check write permissions in recording directory
- Ensure user/container user has access

## Automation

Tests can also be run programmatically:

```python
from app.services.test_service import test_service

# Run all tests
results = await test_service.run_all_tests()

# Only critical tests
health = await quick_health_check()
```

## Logs and Debugging

The test system creates detailed logs for each test execution. When errors occur, additional debug information is provided.

For advanced diagnostics:
1. Check log output in admin panel
2. Increase log lines for more details
3. Filter by ERROR or WARNING level

## Admin Panel Access

The admin panel is available at `/admin` in the StreamVault web application. There you'll find:

- **Dashboard**: Overview of current system status
- **Tests**: All available tests with one-click execution
- **System Info**: Detailed system information
- **Maintenance**: Tools for system maintenance and cleanup
- **Logs**: Live log viewer with search and filter functions

The system is designed to be useful for both developers and administrators monitoring and maintaining StreamVault installations.
