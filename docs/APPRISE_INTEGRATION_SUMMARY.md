# Apprise Integration for Recording Events - Summary

## Overview

Extend existing Apprise notification system to support recording events (started, failed, completed) with configurable settings.

**Current Status:** ✅ Stream events (online/offline/update) already implemented  
**Goal:** Add recording events (started/failed/completed)

---

## What's Already Implemented

### Existing Infrastructure

**File: `app/services/notifications/external_notification_service.py`**
- ✅ Supports 100+ services: Discord, Telegram, Ntfy, Pushover, Slack, Matrix
- ✅ Methods: `send_notification()`, `send_stream_notification()`, `send_test_notification()`
- ✅ Service-specific URL configuration (`_get_service_specific_url()`)
- ✅ Profile image handling (HTTP URLs only)

**Current Event Types:**
- ✅ `online` - Streamer went live
- ✅ `offline` - Streamer went offline
- ✅ `update` - Stream title/category changed
- ✅ `favorite_category` - Streamer started favorite category

**GlobalSettings Model:**
```python
class GlobalSettings(Base):
    notification_url: Optional[str]
    notifications_enabled: bool
    notify_online_global: bool
    notify_offline_global: bool
    notify_update_global: bool
    notify_favorite_category_global: bool
```

---

## What Needs to Be Added

### New Event Types

Add support for 3 new recording events:
- `recording_started` - Recording successfully started
- `recording_failed` - Recording failed (Streamlink crash, proxy error, etc.)
- `recording_completed` - Recording finished successfully

### Required Changes

#### 1. Database Migration (Migration 028)

```python
# Add to global_settings table
notify_recording_started: bool = False   # Default: OFF (noisy)
notify_recording_failed: bool = True     # Default: ON (CRITICAL)
notify_recording_completed: bool = False # Default: OFF (noisy)
```

**Rationale for defaults:**
- `started`: Every live stream triggers recording → too many notifications
- `failed`: **Critical issue** user needs to know immediately → **ON by default**
- `completed`: Most recordings complete normally → too many notifications

#### 2. New Method: `send_recording_notification()`

Add to `external_notification_service.py`:

```python
async def send_recording_notification(
    self, 
    streamer_name: str, 
    event_type: str,  # 'recording_started', 'recording_failed', 'recording_completed'
    details: dict = None
) -> bool:
    """Send notification for recording events"""
    
    # Check if event type is enabled
    if event_type == "recording_started" and not settings.notify_recording_started:
        return False
    elif event_type == "recording_failed" and not settings.notify_recording_failed:
        return False
    elif event_type == "recording_completed" and not settings.notify_recording_completed:
        return False
    
    # Format notification
    title, message = self.formatter.format_recording_notification(
        streamer_name, event_type, details
    )
    
    # Send via Apprise
    return await apprise.async_notify(title=title, body=message)
```

#### 3. Notification Formatting

Add to `notification_formatter.py`:

```python
def format_recording_notification(self, streamer_name: str, event_type: str, details: dict):
    if event_type == "recording_started":
        title = f"🔴 Recording Started: {streamer_name}"
        message = f"Quality: {details['quality']}\nTitle: {details['stream_title']}"
    
    elif event_type == "recording_failed":
        title = f"❌ Recording Failed: {streamer_name}"
        message = f"Error: {details['error_message']}\nTime: {details['timestamp']}"
    
    elif event_type == "recording_completed":
        title = f"✅ Recording Completed: {streamer_name}"
        message = f"Duration: {details['duration_minutes']} min\nSize: {details['file_size_mb']} MB"
    
    return title, message
```

#### 4. Process Manager Integration

**On Recording Start:**
```python
# process_manager.py - start_recording()
await notification_service.send_recording_notification(
    streamer_name=stream.streamer.username,
    event_type='recording_started',
    details={'quality': quality, 'stream_title': stream.title}
)
```

**On Recording Failure:**
```python
# process_manager.py - _monitor_streamlink_process()
if process.returncode != 0:
    # Update database
    recording.status = 'failed'
    
    # WebSocket notification
    await self._notify_recording_failed(stream, error_message)
    
    # Apprise notification (NEW)
    await notification_service.send_recording_notification(
        streamer_name=stream.streamer.username,
        event_type='recording_failed',
        details={'error_message': error_message, 'timestamp': now}
    )
```

**On Recording Completion:**
```python
# process_manager.py - _finalize_recording()
await notification_service.send_recording_notification(
    streamer_name=stream.streamer.username,
    event_type='recording_completed',
    details={
        'duration_minutes': duration_minutes,
        'file_size_mb': file_size_mb,
        'quality': recording.quality
    }
)
```

#### 5. Frontend UI Extension

**Add to `NotificationSettingsPanel.vue`:**

```vue
<div class="settings-section">
  <h3>System Notifications</h3>
  <p>Configure which recording events trigger external notifications.</p>
  
  <div class="toggle-row">
    <input type="checkbox" v-model="systemSettings.notify_recording_started" />
    <span>Recording Started (may be noisy)</span>
  </div>
  
  <div class="toggle-row critical">
    <input type="checkbox" v-model="systemSettings.notify_recording_failed" />
    <span>Recording Failed ⚠️ (RECOMMENDED)</span>
  </div>
  
  <div class="toggle-row">
    <input type="checkbox" v-model="systemSettings.notify_recording_completed" />
    <span>Recording Completed</span>
  </div>
</div>
```

#### 6. API Endpoint Updates

**GET `/api/settings`:**
```python
return {
    # ... existing fields ...
    "notify_recording_started": settings.notify_recording_started,
    "notify_recording_failed": settings.notify_recording_failed,
    "notify_recording_completed": settings.notify_recording_completed
}
```

**PUT `/api/settings`:**
```python
if "notify_recording_started" in settings_data:
    settings.notify_recording_started = settings_data["notify_recording_started"]
if "notify_recording_failed" in settings_data:
    settings.notify_recording_failed = settings_data["notify_recording_failed"]
if "notify_recording_completed" in settings_data:
    settings.notify_recording_completed = settings_data["notify_recording_completed"]
```

---

## Implementation Checklist

### Backend (1 hour)

- [ ] Create Migration 028 (`migrations/028_add_system_notification_settings.py`)
- [ ] Update `app/models.py` - Add 3 new columns to GlobalSettings
- [ ] Add `send_recording_notification()` to `external_notification_service.py`
- [ ] Add `format_recording_notification()` to `notification_formatter.py`
- [ ] Update `get_event_title_map()` with recording event titles
- [ ] Integrate notification calls in `process_manager.py`:
  - Recording start → `send_recording_notification('recording_started')`
  - Recording failure → `send_recording_notification('recording_failed')`
  - Recording completion → `send_recording_notification('recording_completed')`

### Frontend (30 minutes)

- [ ] Update `NotificationSettingsPanel.vue` - Add "System Notifications" section
- [ ] Add 3 toggle switches for recording events
- [ ] Load/save system notification settings
- [ ] Add Toast feedback on settings save
- [ ] Test toggle persistence after page refresh

### API (15 minutes)

- [ ] Update `app/routes/settings.py` GET endpoint - Return new fields
- [ ] Update `app/routes/settings.py` PUT endpoint - Save new fields
- [ ] Test API with Postman/curl

---

## Testing Plan

### Unit Tests
- [ ] Test `send_recording_notification()` with enabled/disabled toggles
- [ ] Test notification formatting for all 3 event types
- [ ] Test service-specific URL generation (ntfy, discord, telegram)
- [ ] Verify profile images are HTTP URLs (not local paths)

### Integration Tests
- [ ] Start recording → Verify Apprise notification sent (if enabled)
- [ ] Kill Streamlink mid-recording → Verify failure notification sent
- [ ] Complete recording → Verify completion notification sent (if enabled)
- [ ] Disable `notify_recording_failed` → Verify NO notification sent
- [ ] Test with multiple services (ntfy + Discord simultaneously)

### Frontend Tests
- [ ] Toggle switches persist after refresh
- [ ] Default settings: started=OFF, failed=ON, completed=OFF
- [ ] Save operation shows success toast
- [ ] Settings load correctly on component mount

### End-to-End Tests
- [ ] Recording fails → WebSocket event + Apprise notification + Toast
- [ ] User receives Discord notification with streamer profile image
- [ ] User receives Telegram notification with error details
- [ ] Multiple notification services work simultaneously

---

## Example Notification Flows

### Scenario 1: Recording Failure (Default Configuration)

**Settings:**
- `notify_recording_failed` = **true** (default)
- Notification URL: `ntfy://ntfy.sh/streamvault`

**Event:**
Streamlink crashes with Proxy 500 error

**Notifications Sent:**
1. **WebSocket**: `recording_failed` event → Frontend updates status
2. **Toast**: "❌ Recording failed: xQc"
3. **Apprise → Ntfy**: 
   - Title: "❌ Recording Failed: xQc"
   - Message: "Error: Streamlink exited with code 1\nTime: 2025-11-12 14:35:12 UTC"
   - Click URL: https://twitch.tv/xqc
   - Profile Image: xQc's avatar
4. **Phone Notification**: User gets ntfy push notification

**Result:** User knows immediately that recording failed, even if not watching StreamVault UI.

---

### Scenario 2: Recording Completed (Custom Configuration)

**Settings:**
- `notify_recording_completed` = **true** (user enabled)
- Notification URL: `discord://webhook_id/webhook_token`

**Event:**
3-hour stream recording completes successfully

**Notifications Sent:**
1. **WebSocket**: `recording_completed` event → Frontend updates status
2. **Toast**: "✅ Recording completed: shroud"
3. **Apprise → Discord**:
   - Title: "✅ Recording Completed: shroud"
   - Message: "Duration: 180 minutes\nFile size: 4250 MB\nQuality: best"
   - Thumbnail: shroud's profile image
   - Embed color: Green

**Result:** User gets Discord notification confirming recording saved successfully.

---

## Supported Notification Services

All existing Apprise services work with recording events:

### Tested Services
- ✅ **Ntfy** - Push notifications (iOS/Android/Desktop)
- ✅ **Discord** - Rich embeds with profile images
- ✅ **Telegram** - Instant messaging with formatting
- ✅ **Matrix** - Encrypted messaging
- ✅ **Slack** - Workspace notifications
- ✅ **Pushover** - Mobile push with priorities

### Configuration Examples

**Ntfy:**
```
ntfy://ntfy.sh/streamvault
```

**Discord:**
```
discord://webhook_id/webhook_token
```

**Telegram:**
```
tgram://bot_token/chat_id
```

**Multiple Services:**
```python
# In NotificationSettingsPanel
notification_url = "ntfy://ntfy.sh/streamvault discord://webhook_id/webhook_token"
# Apprise sends to BOTH services
```

---

## Benefits

### For Users
- ✅ **Never miss critical failures** - Get notified immediately when recording fails
- ✅ **Multi-device notifications** - Phone, desktop, smartwatch
- ✅ **No constant monitoring** - Apprise notifies when issues occur
- ✅ **Configurable verbosity** - Enable only critical events (failed) or all events

### For Developers
- ✅ **Reuses existing infrastructure** - No new notification system needed
- ✅ **Consistent API** - Same pattern as stream notifications
- ✅ **Easy to extend** - Add new event types with minimal code
- ✅ **Service-agnostic** - Works with 100+ notification services

### For Production
- ✅ **Fail-fast visibility** - Issues detected and reported immediately
- ✅ **Reduced manual monitoring** - Automation handles notifications
- ✅ **Audit trail** - All recording events can be logged/tracked
- ✅ **User trust** - Transparency about recording status

---

## Time Estimate

**Total Implementation Time: ~2 hours**

- Migration 028 creation + testing: 15 min
- Backend service extension: 30 min
- Frontend UI extension: 30 min
- API endpoint updates: 15 min
- Integration testing: 30 min

**Priority Level: HIGH** (but not blocking)
- Can be implemented after Recording Failure Detection (CRITICAL)
- Enhances Recording Failure Detection with external notifications
- Low risk, high value

---

## See Also

- Full implementation details: `docs/BACKEND_FEATURES_PLANNED.md` Section 7
- Toast vs WebSocket best practices: `docs/TOAST_VS_WEBSOCKET_BEST_PRACTICES.md`
- Existing Apprise code: `app/services/notifications/external_notification_service.py`
- Notification settings UI: `app/frontend/src/components/settings/NotificationSettingsPanel.vue`
