# StreamVault Background Queue Fixes

## Production Issues Fixed

This document describes the fixes implemented for three critical production issues:

1. **Recording jobs stuck at 100% running** - Jobs complete but stay visible as running in the UI
2. **Orphaned recovery check running continuously** - Should only run once at startup
3. **Task names showing as "Unknown"** - UI doesn't display proper task types

## 🔧 Files Modified

### Core Fixes

#### 1. `app/services/recording_lifecycle_manager.py`
**Problem:** External tasks not properly completed, causing UI to show stuck recordings.

**Fix:** Enhanced `_handle_recording_completion()` and `_handle_recording_error()` to:
- Properly complete external tasks with `background_queue_service.complete_external_task()`
- Remove tasks from progress tracker to prevent UI showing as stuck
- Added detailed logging for troubleshooting

```python
# Enhanced external task completion
self.background_queue_service.complete_external_task(task_id, success=True)
self.background_queue_service.progress_tracker.remove_external_task(task_id)
```

#### 2. `app/events/database_event_orphaned_recovery.py`
**Problem:** Orphaned recovery check triggered continuously after post-processing.

**Fix:** Modified `on_post_processing_completed()` to only log completion instead of triggering new checks:
```python
# Before: Triggered new orphaned recovery
# await orphaned_recovery_service.check_for_orphaned_recordings()

# After: Only logs completion
logger.info(f"✅ Post-processing completed for recording {recording_id}")
```

#### 3. `app/frontend/src/components/BackgroundQueueMonitor.vue`
**Problem:** Task names displayed as "Unknown" due to poor type formatting.

**Fix:** Enhanced `formatTaskType()` function with:
- Support for `orphaned_recovery_check` tasks
- Better fallback formatting for unknown types
- Improved task object handling
- Updated template calls to pass task objects

```javascript
formatTaskType(taskType, task = null) {
  const typeMap = {
    'recording': 'Recording',
    'mp4_remux': 'MP4 Conversion',
    'metadata_generation': 'Metadata',
    'thumbnail_generation': 'Thumbnail',
    'orphaned_recovery_check': 'Recovery Check',
    'cleanup': 'Cleanup'
  };
  
  if (typeMap[taskType]) {
    return typeMap[taskType];
  }
  
  // Enhanced fallback formatting
  return taskType ? taskType.split('_').map(word => 
    word.charAt(0).toUpperCase() + word.slice(1)
  ).join(' ') : 'Unknown Task';
}
```

### Additional Tools

#### 4. `app/services/background_queue_cleanup_service.py` *(New)*
**Purpose:** Comprehensive cleanup service for stuck tasks and issues.

**Features:**
- `cleanup_stuck_recording_tasks()` - Finds and cleans recordings stuck at 100% or running too long
- `stop_continuous_orphaned_recovery()` - Cancels continuous orphaned recovery checks
- `fix_unknown_task_names()` - Infers and fixes task types showing as "Unknown"
- `comprehensive_cleanup()` - Runs all cleanup operations

#### 5. `app/routes/admin_background_queue.py` *(New)*
**Purpose:** Admin API endpoints for manual cleanup.

**Endpoints:**
- `POST /admin/cleanup/background-queue` - Run comprehensive cleanup
- `POST /admin/cleanup/stuck-recordings` - Fix only stuck recordings
- `POST /admin/cleanup/orphaned-recovery` - Stop orphaned recovery
- `POST /admin/cleanup/task-names` - Fix unknown task names
- `GET /admin/status/background-queue` - Check current status

#### 6. `fix_background_queue.py` *(New)*
**Purpose:** Command-line tool for fixing background queue issues.

**Usage:**
```bash
# Run all fixes
python fix_background_queue.py

# Fix specific issues
python fix_background_queue.py --stuck      # Stuck recordings only
python fix_background_queue.py --orphaned   # Orphaned recovery only
python fix_background_queue.py --names      # Unknown names only
python fix_background_queue.py --status     # Show current status
```

## 🧪 Testing the Fixes

### Manual Testing

1. **Check current status:**
   ```bash
   python fix_background_queue.py --status
   ```

2. **Run comprehensive fix:**
   ```bash
   python fix_background_queue.py
   ```

3. **Verify via API:**
   ```bash
   curl -X GET "http://localhost:8000/admin/status/background-queue" \
        -H "X-Admin-Key: your-admin-key"
   ```

### Expected Results

After applying fixes:
- ✅ Recording jobs complete and disappear from UI when finished
- ✅ Orphaned recovery check runs only once at startup
- ✅ Task names display properly (Recording, MP4 Conversion, etc.)
- ✅ No tasks stuck at 100% indefinitely
- ✅ Clean background queue status

## 🔍 Debugging

### Check Background Queue Status
Use the status command to see current issues:
```bash
python fix_background_queue.py --status
```

### Log Messages to Watch For
- `🧹 CLEANUP_STUCK_TASK: recording_xyz (at 100% for 45.2m)`
- `✅ EXTERNAL_TASK_COMPLETED: recording_xyz marked as completed`
- `🛑 STOPPED_ORPHANED_CHECK: Cancelled orphaned recovery task`
- `🔧 FIXED_TASK_TYPE: task_abc -> recording`

### Common Issues
1. **Tasks still showing as stuck:** Re-run cleanup and check external task completion
2. **Orphaned recovery still running:** Check active tasks and cancel manually
3. **Names still showing as Unknown:** Verify task type inference logic

## 🚀 Deployment

1. Deploy the modified files to production
2. Restart the StreamVault application
3. Run the cleanup script once: `python fix_background_queue.py`
4. Monitor logs for successful cleanup messages
5. Verify UI shows proper task states and names

## 🔧 Configuration

No configuration changes required. The fixes are automatic and run with existing background queue service.

## 📝 Future Improvements

1. **Automated Cleanup:** Consider adding periodic cleanup to prevent issues
2. **Better Task Tracking:** Enhance external task lifecycle management
3. **UI Enhancements:** Add real-time task status indicators
4. **Monitoring:** Add alerts for stuck tasks
5. **Prevention:** Improve task completion guarantees

---

**Summary:** These fixes address all three production issues by enhancing external task completion, preventing continuous orphaned recovery, and improving task name display. The cleanup service and admin endpoints provide tools for manual intervention when needed.
