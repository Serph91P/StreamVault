# Post-Processing Management - Admin Interface

## 🎯 Overview

The Post-Processing Management provides a user-friendly admin interface for manually starting post-processing for failed recordings and cleaning up orphaned files.

## 🚀 Features

### Statistics
- **Orphaned .ts Files**: Number of .ts files without corresponding .mp4 files
- **Orphaned Segments**: Number of segment directories without corresponding .mp4 files  
- **Total Size**: Storage space occupied by orphaned files
- **By Streamer**: Breakdown of orphaned files per streamer

### Actions
- **🔍 Preview All Changes**: Shows what would be processed (Dry Run)
- **🔄 Retry All Post-Processing**: Restarts post-processing for all orphaned recordings
- **🧹 Preview Segment Cleanup**: Shows which segment directories would be cleaned
- **🧹 Clean Orphaned Segments**: Deletes orphaned segment directories

### Detailed Recordings List
- **📋 Load List**: Loads detailed list of all orphaned recordings
- **Selection**: Select individual recordings for processing
- **🔄 Retry Selected**: Start post-processing only for selected recordings

## 📊 Usage

### Basic Workflow:

1. **Check Statistics**: Click "🔄 Refresh" to load current statistics
2. **Use Preview**: Use "🔍 Preview All Changes" to see what would be processed
3. **Start Post-Processing**: Click "🔄 Retry All Post-Processing" to process all orphaned recordings
4. **Clean Segments**: Use "🧹 Clean Orphaned Segments" to remove no longer needed segment directories

### Advanced Options:

- **Max Age (hours)**: Determines the maximum age of recordings to be processed (default: 48h)
- **Specific Selection**: Load the detailed list and select only specific recordings

## 🔧 API Endpoints

The Post-Processing Management uses the following new API endpoints:

### Statistics
```
GET /api/admin/post-processing/stats?max_age_hours=48
```

### Retry All Post-Processing
```
POST /api/admin/post-processing/retry-all?max_age_hours=48&dry_run=false&cleanup_segments=true
```

### Process Specific Recordings
```
POST /api/admin/post-processing/retry-specific
{
  "recording_ids": [123, 456, 789],
  "dry_run": false
}
```

### Clean Segment Directories
```
POST /api/admin/post-processing/cleanup-segments?max_age_hours=48&dry_run=false
```

### List Orphaned Recordings
```
GET /api/admin/post-processing/orphaned-list?max_age_hours=48&limit=100
```

### Manual Post-Processing
```
POST /api/admin/post-processing/enqueue-manual?recording_id=123&ts_file_path=/path/to/file.ts&streamer_name=example&force=false
```

## 🛡️ Security

- **Admin Authentication**: All endpoints are only accessible through the Admin interface
- **Confirmation Dialogs**: Destructive actions require confirmation
- **Dry Run Mode**: Allows preview without actual changes
- **Logging**: All actions are logged

## 📝 Common Use Cases

### Problem: .ts files without .mp4
**Cause**: Post-processing failed after recording
**Solution**: Use "🔄 Retry All Post-Processing"

### Problem: Segment directories remain
**Cause**: Concatenation or cleanup failed
**Solution**: Use "🧹 Clean Orphaned Segments"

### Problem: Specific recording not processed
**Cause**: Individual recording problem
**Solution**: Load detailed list and select specific recording

## 🔍 Troubleshooting

### Error Messages
- **"File not found"**: .ts file no longer exists in filesystem
- **"MP4 already exists"**: Post-processing already completed successfully
- **"Too recent"**: File is too new (< 30 minutes) and is skipped
- **"File too small"**: File is too small (< 1MB) and considered invalid

### Logging
All Post-Processing Management actions are logged with the following prefixes:
- `🔄 ADMIN_RETRY_ALL_POST_PROCESSING:` - Retry all post-processing
- `🎯 ADMIN_RETRY_SPECIFIC:` - Process specific recordings
- `🧹 ADMIN_CLEANUP_SEGMENTS:` - Segment cleanup
- `📊 ADMIN_POST_PROCESSING_STATS:` - Load statistics
- `⚡ ADMIN_MANUAL_ENQUEUE:` - Manual post-processing

## ⚙️ Configuration

The system uses the same configuration parameters as the automatic Orphaned Recovery Service:

- **Max Age**: Default 48 hours for orphaned recordings
- **Min File Size**: 1MB minimum size for valid recordings
- **Recent Threshold**: 30 minutes for "too new" files
- **Segment Pattern**: `*_segments` directories are recognized as segment folders

## 🔗 Integration

The Post-Processing Management is fully integrated into the existing StreamVault architecture:

- **Orphaned Recovery Service**: Uses the same service as automatic recovery
- **Background Queue**: Utilizes the existing task queue system
- **Database**: Works with existing Recording/Stream/Streamer models
- **WebSocket**: Sends updates through the existing WebSocket system

## 🎯 Benefits

✅ **No technical knowledge required** - One-click solution
✅ **Directly in the application** - No Docker/Terminal needed
✅ **Real-time status** - Immediate problem resolution
✅ **User-friendly** - Clear interface with confirmation dialogs
✅ **Automatic detection** - Finds orphaned files automatically
✅ **Detailed feedback** - Shows exactly what was processed

The Post-Processing Management feature makes recording recovery accessible to all users without requiring technical expertise!
