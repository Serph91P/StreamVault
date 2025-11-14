# Multi-Proxy System with Health Checks

## 🔴 Priority: CRITICAL
**Status:** 🔴 NOT STARTED  
**Estimated Time:** 3-4 hours  
**Sprint:** Sprint 1 - Hotfix Priority  
**Impact:** HIGH - Prevents recording failures, blocks production

---

## 📝 Problem Description

### Current Situation (Production Issue)

**Single Point of Failure:**
- **Current Setup:** Only 1 proxy configured in database (`global_settings.http_proxy`)
- **Status:** ❌ Proxy currently **DOWN** (500 Internal Server Error since November 12, 2025)
- **Result:** 🚨 **ALL recordings fail** after ~1 minute
- **Fallback:** None - if proxy fails, entire recording system is unusable

**Error Pattern (from Production Logs):**
```
2025-11-12 14:23:45 - streamvault - ERROR - 🔴 PROXY_DOWN: Cannot start recording for StreamerName: Proxy connection failed - connection refused
2025-11-12 14:23:45 - streamvault - ERROR - ProcessError: Proxy connection failed. Please check proxy settings or network connectivity.
```

**Impact Analysis:**
- ⏹️ **0 recordings** completed since proxy failure
- 📺 **15+ streamers** monitored but not recording
- 🕒 **24+ hours** of lost content (November 12-13)
- 🔧 **Manual intervention required** → User must find new proxy, update settings, restart app

### Root Cause: Single Proxy Architecture

**Streamlink Limitation:**
- Streamlink only supports **ONE proxy at a time** via `--http-proxy` argument
- No built-in health checking
- No automatic failover
- If proxy becomes unreachable → recording process hangs or fails

**Current Database Schema:**
```
GlobalSettings table:
- http_proxy: VARCHAR (only 1 proxy URL!)
- https_proxy: VARCHAR (only 1 proxy URL!)
```

**Current Implementation Location:**
- File: `app/utils/streamlink_utils.py` (line ~385)
- Function: `get_proxy_settings_from_db()`
- Returns: Single proxy from `global_settings.http_proxy`

**Problems:**
1. ❌ **No redundancy** - if proxy fails, entire system fails
2. ❌ **No health monitoring** - don't know proxy status until recording fails
3. ❌ **No automatic switching** - requires manual proxy change + app restart
4. ❌ **No fallback** - can't use direct connection when proxy is down
5. ❌ **Manual recovery** - user must find alternative proxy manually

### User Experience Impact

**Scenario: Proxy Goes Down Mid-Operation**
1. ✅ User adds streamer → EventSub webhook registers
2. ✅ Streamer goes live → EventSub triggers `stream.online`
3. ✅ Recording starts → Proxy connectivity check passes
4. ✅ Stream records for 1 minute
5. ❌ **Proxy fails** (500 error, network issue, timeout)
6. ❌ Streamlink process hangs → Recording stops
7. ❌ No fallback proxy → Content lost
8. 🔧 **User must manually:**
   - Notice recordings failing (check logs or UI)
   - Find alternative proxy service
   - Update Settings → Proxy URL
   - Restart application
   - **Time to Recover:** 10-30 minutes
   - **Content Lost:** All streams during downtime

---

## 🎯 Solution: Multi-Proxy System with Health Checks

### Overview

Implement **application-level proxy management** with:
- Multiple proxies stored in database
- Automatic health monitoring (periodic checks)
- Intelligent proxy selection (best available)
- Graceful failover (direct connection as last resort)
- Real-time status updates to frontend

### Architecture Flow

```
┌─────────────────────────────────────────────────────┐
│         Recording Starts (ProcessManager)           │
│                                                      │
│  1. Check if proxy enabled in settings              │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│       ProxyHealthService.get_best_proxy()            │
│                                                       │
│  2. Query database for enabled proxies               │
│  3. Filter by health_status (healthy > degraded)     │
│  4. Sort by priority (0 = highest)                   │
│  5. Sort by response_time_ms (faster = better)       │
│  6. Return best proxy URL                            │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│         Database: proxy_settings Table               │
│                                                       │
│ ┌─────────────────────────────────────────────────┐ │
│ │ id | proxy_url           | health   | enabled │ │
│ │ 1  | http://proxy1:9999  | healthy  | TRUE    │ │
│ │ 2  | http://proxy2:8080  | failed   | FALSE   │ │
│ │ 3  | http://proxy3:3128  | degraded | TRUE    │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Background Task: ProxyHealthService.run_checks()    │
│                                                       │
│  Runs every 5 minutes:                               │
│  - Test each enabled proxy (Twitch API endpoint)     │
│  - Measure response time (milliseconds)              │
│  - Update health_status (healthy/degraded/failed)    │
│  - Track consecutive_failures counter                │
│  - Auto-disable after 3 consecutive failures         │
│  - Broadcast status updates via WebSocket            │
└─────────────────────────────────────────────────────┘
```

### Key Features

**1. Multi-Proxy Management:**
- Store multiple proxy URLs in database
- Priority ranking (0 = highest priority, 1 = backup, 2 = last resort)
- Enable/Disable proxies individually
- Add/Remove proxies via UI or API

**2. Automatic Health Monitoring:**
- Background task runs every 5 minutes
- Tests connectivity with Twitch API endpoint
- Measures response time (milliseconds)
- Categorizes status: `healthy`, `degraded`, `failed`, `unknown`
- Tracks consecutive failure count
- Auto-disables proxy after 3 consecutive failures

**3. Intelligent Proxy Selection:**
- Selection algorithm:
  1. Filter: Only enabled proxies
  2. Prioritize: healthy > degraded > failed
  3. Sort by: priority field (ascending)
  4. Sort by: response_time_ms (ascending)
  5. Return: Best available proxy
- Falls back to direct connection if all proxies fail (configurable)

**4. Real-Time Status Updates:**
- WebSocket broadcasts proxy health changes
- Frontend shows live proxy status
- Health badges: ✅ healthy, ⚠️ degraded, ❌ failed, ❓ unknown
- Response time displayed (e.g., "123ms")

**5. Statistics Tracking:**
- Total recordings using each proxy
- Failed recordings count
- Success rate calculation
- Average response time

---

## 📋 Required Changes

### Database Schema Changes

**New Table: `proxy_settings`**

Columns needed:
- `id` - Primary key (serial)
- `proxy_url` - Full proxy URL (format: `http://username:password@host:port`)
- `priority` - Priority ranking (0 = highest, lower number = higher priority)
- `enabled` - Active status (boolean)
- `last_health_check` - Timestamp of last health test
- `health_status` - Current health: healthy/degraded/failed/unknown
- `consecutive_failures` - Failure counter (for auto-disable)
- `average_response_time_ms` - Response time in milliseconds
- `total_recordings` - How many times used
- `failed_recordings` - How many times failed
- `success_rate` - Calculated: (total - failed) / total
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

**Indexes needed:**
- Index on `enabled` (filter enabled proxies quickly)
- Index on `health_status` (filter by health quickly)
- Index on `priority` (sorting)

**Migration tasks:**
1. Create `proxy_settings` table with all columns
2. Create indexes
3. Migrate existing proxy from `global_settings.http_proxy` (if exists) as priority 0
4. Add new columns to `recording_settings` table

**New Columns in `recording_settings`:**
- `enable_proxy` - Master switch for proxy system (boolean, default TRUE)
- `proxy_health_check_enabled` - Enable automatic health checks (boolean, default TRUE)
- `proxy_health_check_interval_seconds` - Check interval (integer, default 300 = 5 minutes)
- `proxy_max_consecutive_failures` - Auto-disable threshold (integer, default 3)
- `fallback_to_direct_connection` - Use direct connection when all proxies fail (boolean, default TRUE)

---

### Backend Components Needed

**1. ProxyHealthService**
- Location: New file `app/services/proxy/proxy_health_service.py`
- Responsibilities:
  - Check proxy connectivity (test with Twitch API endpoint)
  - Measure response time
  - Return health status: healthy/degraded/failed
  - Select best available proxy
  - Run periodic health checks (background task)
  - Auto-disable proxies after consecutive failures
  - Broadcast health updates via WebSocket

**Key Methods Needed:**
- `check_proxy_health(proxy_url)` - Test single proxy, return status + response_time
- `get_best_proxy()` - Return best available proxy URL or None
- `run_health_checks()` - Background task (infinite loop with 5 min sleep)
- `start()` - Start background task
- `stop()` - Stop background task gracefully

**Health Check Logic:**
- Use `httpx.AsyncClient` with proxy settings
- Test endpoint: `https://api.twitch.tv/helix/streams`
- Timeout: 10 seconds
- Status codes:
  - 200 = healthy
  - 4xx = degraded (proxy works but request invalid)
  - 5xx = failed (proxy or upstream error)
  - Timeout = failed
  - Exception = failed

---

**2. ProcessManager Updates**
- Location: Existing file `app/services/recording/process_manager.py`
- Current behavior: Gets single proxy from `get_proxy_settings_from_db()` (line ~172)
- Required changes:
  - Check if proxy enabled in `recording_settings.enable_proxy`
  - Call `ProxyHealthService.get_best_proxy()` instead
  - Use returned proxy for Streamlink command
  - Fallback to direct connection if no healthy proxies (if `fallback_to_direct_connection=True`)
  - Raise error if no proxies and fallback disabled
  - Log proxy selection decision

---

**3. API Endpoints**
- Location: New file `app/routes/proxy.py`
- Endpoints to create:

**GET `/api/proxy/list`**
- Returns: List of all configured proxies with health status
- Response includes: id, proxy_url (masked), priority, enabled, health_status, response_time, statistics
- Security: Mask password in proxy_url (show `http://user:***@host:port`)

**POST `/api/proxy/add`**
- Parameters: proxy_url (required), priority (optional, default 0)
- Validates: URL format (must start with http:// or https://)
- Creates: New proxy entry with status "unknown"
- Triggers: Immediate health check
- Returns: success + proxy_id

**DELETE `/api/proxy/{proxy_id}`**
- Removes: Proxy from database
- Returns: success

**POST `/api/proxy/{proxy_id}/toggle`**
- Toggles: enabled status (true ↔ false)
- Resets: consecutive_failures to 0 when re-enabling
- Returns: success + new enabled status

**POST `/api/proxy/{proxy_id}/test`**
- Triggers: Manual health check immediately
- Updates: Database with result
- Returns: health status + response_time

**POST `/api/proxy/{proxy_id}/update-priority`**
- Parameters: priority (integer)
- Updates: Proxy priority for sorting
- Returns: success

---

**4. Model Updates**
- Location: Existing file `app/models.py`
- New model class: `ProxySettings` (with all columns listed above)
- Updated model class: `RecordingSettings` (add 5 new proxy config columns)

---

**5. Application Startup**
- Location: Existing file `app/main.py`
- Changes needed:
  - Register proxy routes from `app.routes.proxy`
  - Create ProxyHealthService singleton
  - Start background health check task on app startup event
  - Stop background task on app shutdown event

---

### Frontend Components Needed

**1. ProxySettingsPanel Component**
- Location: New file `app/frontend/src/components/settings/ProxySettingsPanel.vue`
- Displayed in: Settings View (new tab or section)

**UI Elements Required:**

**System Status Header:**
- Shows overall proxy system status with colored indicator
- Possible states:
  - ✅ HEALTHY: "X of Y proxies healthy"
  - ⚠️ DEGRADED: "All proxies down - using direct connection fallback"
  - ❌ ERROR: "All proxies down - recordings will fail"
  - 🔌 DISABLED: "Proxy system disabled - using direct connection"

**Proxy List (Table or Cards):**
- Columns/Fields:
  - Proxy URL (masked: `http://user:***@host:port`)
  - Priority (0, 1, 2, etc.)
  - Health Status Badge (✅/⚠️/❌/❓)
  - Response Time (e.g., "123ms" or "Timeout")
  - Last Check Time (e.g., "2 minutes ago")
  - Consecutive Failures Count
  - Actions: Test, Enable/Disable, Delete

**Add Proxy Button:**
- Opens: Dialog/modal with form
- Input fields:
  - Proxy URL (text field with validation)
  - Priority (number field, default 0)
- Validation: URL must start with http:// or https://
- On submit: Creates proxy + triggers health check
- Shows: Success/error toast message

**Advanced Settings (Collapsible Section):**
- Enable Proxy System (toggle switch)
- Health Check Interval (number input, minutes)
- Max Consecutive Failures (number input, 1-10)
- Fallback to Direct Connection (toggle switch)

---

**2. Composable**
- Location: New file `app/frontend/src/composables/useProxySettings.ts`
- Purpose: Manage proxy settings state and API calls

**State to manage:**
- `proxies` - Array of proxy objects
- `config` - Proxy configuration object
- `isLoading` - Boolean loading state
- `error` - Error message string

**Computed Properties:**
- `healthyProxyCount` - Count of healthy enabled proxies
- `proxySystemStatus` - Overall system status object

**Methods to implement:**
- `fetchProxies()` - Load all proxies from API
- `addProxy(url, priority)` - Add new proxy
- `deleteProxy(id)` - Remove proxy
- `toggleProxy(id)` - Enable/disable proxy
- `testProxy(id)` - Trigger manual health check
- `updatePriority(id, priority)` - Change priority

**WebSocket Integration:**
- Subscribe to `proxy_health_update` events
- Update proxy list in real-time when health changes

---

**3. TypeScript Types**
- Location: New file `app/frontend/src/types/proxy.ts`
- Interfaces to define:
  - `ProxySettings` - Proxy object structure
  - `ProxyHealthCheckResult` - Health check result structure
  - `ProxyConfigSettings` - Configuration options structure

---

## 📂 Files to Create

**Backend (4 files):**
1. `migrations/025_add_multi_proxy_support.py` - Database migration script
2. `app/services/proxy/__init__.py` - Package init file
3. `app/services/proxy/proxy_health_service.py` - Health check service class
4. `app/routes/proxy.py` - API endpoints

**Frontend (3 files):**
1. `app/frontend/src/types/proxy.ts` - TypeScript interfaces
2. `app/frontend/src/composables/useProxySettings.ts` - Proxy composable
3. `app/frontend/src/components/settings/ProxySettingsPanel.vue` - UI component

---

## 📂 Files to Modify

**Backend (3 files):**
1. `app/models.py` - Add ProxySettings model + update RecordingSettings
2. `app/services/recording/process_manager.py` - Use proxy selection instead of hardcoded
3. `app/main.py` - Register routes + start/stop health service

**Frontend (1 file):**
1. `app/frontend/src/views/SettingsView.vue` - Add ProxySettingsPanel tab/section

---

## ✅ Acceptance Criteria

### Database
- [ ] `proxy_settings` table exists with all required columns
- [ ] Indexes created on enabled, health_status, priority
- [ ] Existing proxy migrated from global_settings (if exists)
- [ ] `recording_settings` has new proxy config columns

### Backend Service
- [ ] ProxyHealthService singleton created and working
- [ ] Health check tests proxy connectivity via Twitch API
- [ ] Response time measured accurately in milliseconds
- [ ] Health status categorized correctly (healthy/degraded/failed)
- [ ] Periodic health checks run automatically every 5 minutes
- [ ] Proxies auto-disable after 3 consecutive failures
- [ ] Best proxy selection algorithm works (healthy > degraded, sorted by priority + response time)
- [ ] Fallback to direct connection works when all proxies fail
- [ ] WebSocket broadcasts health updates to connected clients

### API Endpoints
- [ ] GET /api/proxy/list returns all proxies with status
- [ ] POST /api/proxy/add creates new proxy successfully
- [ ] DELETE /api/proxy/{id} removes proxy from database
- [ ] POST /api/proxy/{id}/toggle enables/disables proxy correctly
- [ ] POST /api/proxy/{id}/test triggers manual health check
- [ ] POST /api/proxy/{id}/update-priority changes priority
- [ ] Password masking works in all API responses

### Process Manager Integration
- [ ] ProcessManager calls get_best_proxy() before starting recording
- [ ] Checks if proxy enabled in settings
- [ ] Uses returned proxy for Streamlink command
- [ ] Falls back to direct connection if all proxies fail (when enabled)
- [ ] Logs proxy selection decisions with clear messages

### Frontend UI
- [ ] ProxySettingsPanel displays system status indicator correctly
- [ ] Proxy list shows all configured proxies
- [ ] Health badges display correctly (✅/⚠️/❌/❓)
- [ ] Add Proxy dialog works and validates input
- [ ] Test button triggers manual health check
- [ ] Enable/Disable toggle works
- [ ] Delete button removes proxy with confirmation
- [ ] Priority ordering visible and modifiable
- [ ] Real-time WebSocket updates reflected in UI without refresh
- [ ] Advanced settings section works (enable proxy, intervals, fallback)

### Integration
- [ ] Recording starts with best available healthy proxy
- [ ] Recording falls back to direct connection when all proxies fail
- [ ] Recording fails gracefully if fallback disabled and no proxies available
- [ ] WebSocket broadcasts proxy status changes to frontend
- [ ] Frontend shows real-time proxy health updates

---

## 🧪 Testing Checklist

### Manual Testing Scenarios

**1. Basic Proxy Management**
- [ ] Add 3 proxies via UI (with priorities 0, 1, 2)
- [ ] Verify proxies appear in list with "unknown" status
- [ ] Click "Test" on each proxy → Status updates to healthy/failed
- [ ] Toggle proxy enabled/disabled → State changes immediately
- [ ] Delete proxy → Removed from list with confirmation
- [ ] Change proxy priority → Order updates in list

**2. Health Check System**
- [ ] Wait 5 minutes after adding proxy → Verify automatic health check runs
- [ ] Check backend logs for health check messages
- [ ] Verify database updated (last_health_check, health_status, response_time)
- [ ] Verify WebSocket messages sent to frontend
- [ ] Verify UI updates automatically without page refresh

**3. Auto-Disable Feature**
- [ ] Manually set proxy to 3 consecutive failures in database
- [ ] Wait for next health check OR trigger manual test
- [ ] Verify proxy auto-disabled (enabled = FALSE)
- [ ] Check logs for "auto-disabled after 3 failures" message
- [ ] Verify WebSocket notification sent to frontend

**4. Proxy Selection Algorithm**
- [ ] Configure: 1 healthy (priority 0), 1 degraded (priority 1), 1 failed (priority 2)
- [ ] Start recording → Check logs for proxy selection
- [ ] Verify healthy proxy (priority 0) selected
- [ ] Disable healthy proxy → Start another recording
- [ ] Verify degraded proxy (priority 1) selected next
- [ ] Disable all proxies → Verify direct connection used (if fallback enabled)

**5. Recording Integration**
- [ ] Add streamer, wait for stream.online event (or trigger manually)
- [ ] Check logs for "Using proxy: http://..." message
- [ ] Verify Streamlink command includes --http-proxy argument
- [ ] Verify recording works successfully with proxy
- [ ] Simulate proxy failure mid-recording → Check error handling

**6. Fallback to Direct Connection**
- [ ] Disable all proxies OR mark all as failed in database
- [ ] Enable fallback in recording_settings
- [ ] Start recording → Verify direct connection used
- [ ] Check logs for "No healthy proxies - using direct connection" warning

**7. WebSocket Updates**
- [ ] Open Settings → Proxy panel in browser
- [ ] Trigger health check (manual test or wait 5 minutes)
- [ ] Verify UI updates without page refresh
- [ ] Check browser console for WebSocket messages
- [ ] Verify health badges change color/icon

**8. Edge Cases**
- [ ] No proxies configured → System uses direct connection
- [ ] All proxies disabled → Fallback to direct or error (based on settings)
- [ ] Fallback disabled + all proxies failed → Recording fails gracefully with error
- [ ] Proxy with invalid URL format → Validation error on add
- [ ] Duplicate proxy URL → Error message (optional: allow duplicates with different priority)
- [ ] Extremely slow proxy (>10s) → Times out and marked as failed

---

## 📖 Documentation References

**Primary Documentation:**
- `docs/BACKEND_FEATURES_PLANNED.md` (Section 2) - Detailed technical implementation notes
- `docs/MASTER_TASK_LIST.md` (Task #3) - High-level overview and progress tracking

**Related Documentation:**
- `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md` - Frontend design patterns
- `docs/DESIGN_SYSTEM.md` - UI component styling reference

**Relevant Code Files (Read Before Implementation):**
- `app/utils/streamlink_utils.py` - Current proxy implementation (single proxy)
- `app/services/recording/process_manager.py` - Where proxy is used for recordings
- `app/models.py` - Current GlobalSettings model with http_proxy column
- `app/services/communication/websocket_manager.py` - WebSocket broadcast pattern

---

## 🚨 Security Considerations

**⚠️ CRITICAL: Proxy Credentials Protection**

Proxy URLs contain sensitive credentials (username, password):
- Format: `http://username:password@proxy-host:9999`

**Security Measures Required:**

**1. Password Masking in API Responses**
- Never return full proxy URL with password in list endpoints
- Implement mask_password() function: Replace password with `***`
- Example masked: `http://username:***@proxy-host:9999`
- Only show full URL in edit dialog (when user needs to update)

**2. Password Masking in Logs**
- Truncate proxy URLs in all log messages
- Example: `logger.info(f"Using proxy: {proxy_url[:50]}...")`
- Never log full proxy URL with credentials at any log level

**3. Database Security (Best Practice)**
- **REQUIRED:** Encrypt proxy credentials in database
- Use application-level encryption key (stored in environment variable)
- Decrypt only when needed (when passing to Streamlink)
- Use Python `cryptography` library with Fernet symmetric encryption
- Database access already secured by application layer
- Backup encryption key securely (document recovery procedure)

**4. Frontend Display**
- Mask passwords in UI table/list views
- Show full URL only in edit dialog with input type="password" for password portion
- Use secure clipboard copy (no password) for sharing

**Example Implementation:**
```
mask_password(url):
  - Split by '@': ['http://user:pass', 'host:port']
  - Replace password: 'http://user:***'
  - Join: 'http://user:***@host:port'
```

---

## 🤖 Copilot Instructions for Implementation

### Context

**Current Problem:**
- Single proxy configured in `global_settings.http_proxy`
- Proxy currently DOWN (500 error)
- ALL recordings fail after ~1 minute
- No fallback mechanism → entire system unusable
- Manual intervention required (find new proxy, update settings, restart)

**Solution Goal:**
Implement multi-proxy system with automatic health checks and failover at application level.

### Architecture Principles

**1. Application-Level Proxy Rotation**
- Streamlink limitation: Only supports 1 proxy per command via `--http-proxy`
- Cannot do mid-recording proxy switching (would require process restart)
- Solution: Select best proxy BEFORE starting recording
- Store multiple proxies in database, health check all, use best available

**2. Health Check Strategy**
- Periodic background task (every 5 minutes via asyncio.sleep)
- Test connectivity: Use Twitch API endpoint (fast, reliable, no auth needed)
- Measure response time in milliseconds
- Auto-disable proxy after 3 consecutive failures
- Broadcast updates via WebSocket to frontend

**3. Proxy Selection Algorithm**
```
1. Filter: Only enabled=TRUE proxies from database
2. Prioritize: healthy > degraded > failed (by health_status)
3. Sort: By priority field (ascending, 0 = highest)
4. Sort: By response_time_ms (ascending, faster = better)
5. Return: First match or None
```

**4. Fallback Strategy**
- If all proxies fail AND `fallback_to_direct_connection=True`: Use direct connection (no proxy)
- If all proxies fail AND `fallback_to_direct_connection=False`: Raise error, recording fails

### Critical Patterns to Follow

**1. Database Transactions**
Always use context manager and commit changes:
```
with SessionLocal() as db:
    proxy = db.query(ProxySettings).first()
    proxy.health_status = "healthy"
    db.commit()  # CRITICAL - without this, changes are lost!
```

**2. Async/Await for I/O**
Health checks must be asynchronous (don't block main thread):
```
async def check_proxy_health(proxy_url):
    async with httpx.AsyncClient(...) as client:
        response = await client.get(...)
    return result
```

**3. Error Handling**
Health check failures should NOT crash the app:
```
try:
    result = await check_proxy_health(proxy_url)
except asyncio.TimeoutError:
    return {"status": "failed", "error": "Timeout"}
except httpx.ProxyError as e:
    return {"status": "failed", "error": str(e)}
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return {"status": "failed", "error": str(e)}
```

**4. Logging**
Use structured logging with emojis for visibility:
```
logger.info(f"✅ Proxy health: {proxy_url[:50]}... - healthy (123ms)")
logger.warning(f"⚠️ No healthy proxies - using degraded: {proxy_url[:50]}...")
logger.error(f"🚨 Proxy auto-disabled after 3 failures: {proxy_url[:50]}...")
```

**5. WebSocket Broadcasting**
Notify frontend of status changes:
```
from app.services.communication.websocket_manager import websocket_manager

await websocket_manager.broadcast({
    "type": "proxy_health_update",
    "proxy": {
        "id": proxy.id,
        "health_status": "healthy",
        "response_time_ms": 123
    }
})
```

**6. Security: Password Masking**
Never expose full proxy URL with credentials:
```
# Truncate in logs
logger.info(f"Using proxy: {proxy_url[:50]}...")

# Mask in API responses
def mask_password(url):
    if '@' in url:
        parts = url.split('@')
        if ':' in parts[0]:
            user_part = parts[0].rsplit(':', 1)[0]
            return f"{user_part}:***@{parts[1]}"
    return url
```

### Dependencies

**Python Packages:**
- `httpx` - Async HTTP client for health checks (already installed)
- `asyncio` - Background tasks for periodic checks (stdlib)

**Database:**
- PostgreSQL (existing)
- New table: `proxy_settings`
- New columns in: `recording_settings`

**External Services:**
- Twitch API - Health check endpoint: `https://api.twitch.tv/helix/streams`
- No authentication needed for basic connectivity test

### Testing Strategy

**Unit Tests:**
- Test ProxyHealthService methods (check_proxy_health, get_best_proxy)
- Mock httpx.AsyncClient for deterministic tests
- Test timeout handling, error handling, status categorization

**Integration Tests:**
- Add 3 proxies (1 working, 2 broken)
- Verify health checks run automatically every 5 minutes
- Verify best proxy selected (healthy > degraded, sorted)
- Verify auto-disable after 3 consecutive failures
- Verify fallback to direct connection works
- Verify WebSocket broadcasts received by frontend

**Manual Testing:**
- Test via browser UI (Settings → Proxy Settings panel)
- Add/Remove/Test/Toggle proxies
- Verify real-time health updates (no page refresh)
- Start recording → Verify proxy used in logs

### Files to Read Before Implementation

**Backend (Must Read):**
1. `app/services/recording/process_manager.py` (line ~171-212) - Current proxy usage
2. `app/utils/streamlink_utils.py` (line ~54-110, ~385-410) - Proxy connectivity check + get_proxy_settings_from_db
3. `app/models.py` (line ~215-237) - Current GlobalSettings model structure
4. `app/services/communication/websocket_manager.py` - WebSocket broadcast pattern

**Frontend (Should Read):**
5. `docs/DESIGN_SYSTEM.md` - UI component patterns and styling
6. `app/frontend/src/views/SettingsView.vue` - Settings panel structure
7. `app/frontend/src/composables/useWebSocket.ts` - WebSocket subscription pattern

### Success Criteria

**Backend Implementation:**
- [ ] Migration 025 creates proxy_settings table successfully
- [ ] ProxySettings model added to models.py
- [ ] RecordingSettings model updated with 5 new proxy config columns
- [ ] ProxyHealthService implemented with all required methods
- [ ] Background health check task runs automatically every 5 minutes
- [ ] Proxies auto-disable after 3 consecutive failures
- [ ] ProcessManager uses get_best_proxy() instead of hardcoded single proxy
- [ ] Fallback to direct connection works when enabled
- [ ] All 6 API endpoints functional and tested

**Frontend Implementation:**
- [ ] ProxySettingsPanel component created with all UI elements
- [ ] Proxy list displays with health badges and response times
- [ ] Add/Remove/Test/Toggle buttons work correctly
- [ ] Real-time WebSocket updates (no page refresh needed)
- [ ] Advanced settings panel functional

**Integration:**
- [ ] Recording starts with best available proxy (logged)
- [ ] Logs show clear proxy selection decision
- [ ] Fallback works when all proxies fail
- [ ] WebSocket broadcasts status changes
- [ ] Frontend updates automatically

### Common Pitfalls to Avoid

**❌ Don't:**
- Hardcode proxy URLs anywhere in code
- Block main thread with synchronous health checks
- Forget to commit database changes after updates
- Let health check failures crash the entire application
- Expose full proxy URLs (with passwords) in logs or API responses
- Use bare `except:` clauses (catch specific exceptions)
- Run health checks too frequently (causes unnecessary load)
- Store proxy credentials in plain text (encrypt in database!)

**✅ Do:**
- Use async/await for all I/O operations (health checks, API calls)
- Catch specific exceptions (TimeoutError, ProxyError, HTTPError)
- Log all proxy selection decisions with clear context
- Mask passwords in logs (truncate) and API responses (replace with ***)
- Encrypt proxy credentials in database with application key
- Test with real proxies (both working and broken)
- Use context managers for database sessions
- Add comprehensive error handling at every layer
- Check proxy health BEFORE starting recording (not mid-recording)
- Implement graceful fallback to direct connection when all proxies fail

---

**End of Issue #2 Documentation**

*This issue is CRITICAL and blocks all production recordings. Implement as Sprint 1 Hotfix with highest priority.*
