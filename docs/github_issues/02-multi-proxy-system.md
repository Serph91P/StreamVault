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

**Problem:**
- Only 1 proxy in database (`global_settings.http_proxy`)
- No health status tracking
- No automatic switching
- Process manager checks connectivity **before** starting, but not **during** recording

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

### Architecture

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
- `proxy_url` - Full proxy URL (e.g., `http://user:pass@host:port`)
- `priority` - Priority ranking (0 = highest, lower number = higher priority)
- `enabled` - Active status (boolean)
- `last_health_check` - Timestamp of last health test
- `health_status` - Current health: healthy/degraded/failed/unknown
- `consecutive_failures` - Failure counter (for auto-disable)
- `average_response_time_ms` - Response time in milliseconds
- `total_recordings` - How many times used
- `failed_recordings` - How many times failed
- `success_rate` - (total - failed) / total
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

**Indexes needed:**
- Index on `enabled` (filter enabled proxies)
- Index on `health_status` (filter by health)
- Index on `priority` (sorting)

**Migration tasks:**
1. Create `proxy_settings` table
2. Migrate existing proxy from `global_settings.http_proxy` (if exists)
3. Add new columns to `recording_settings` table for proxy configuration

**New Columns in `recording_settings`:**
- `enable_proxy` - Master switch for proxy system (boolean, default TRUE)
- `proxy_health_check_enabled` - Enable automatic health checks (boolean, default TRUE)
- `proxy_health_check_interval_seconds` - Check interval (integer, default 300)
- `proxy_max_consecutive_failures` - Auto-disable threshold (integer, default 3)
- `fallback_to_direct_connection` - Use direct connection when all proxies fail (boolean, default TRUE)

---

### Backend Components Needed

**1. ProxyHealthService**
- Location: New file `app/services/proxy/proxy_health_service.py`
- Responsibilities:
  - Check proxy connectivity (test with Twitch API)
  - Measure response time
  - Return health status: healthy/degraded/failed
  - Select best available proxy
  - Run periodic health checks (background task)
  - Auto-disable proxies after consecutive failures
  - Broadcast health updates via WebSocket

**Key Methods:**
- `check_proxy_health(proxy_url)` - Test single proxy, return status + response_time
- `get_best_proxy()` - Return best available proxy URL or None
- `run_health_checks()` - Background task (runs every 5 minutes)
- `start()` - Start background task
- `stop()` - Stop background task

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
- Change needed: Replace hardcoded proxy with proxy selection
- Current behavior: Gets single proxy from `get_proxy_settings_from_db()`
- New behavior:
  - Check if proxy enabled in settings
  - Call `ProxyHealthService.get_best_proxy()`
  - Use returned proxy for Streamlink command
  - Fallback to direct connection if no healthy proxies
  - Log proxy selection decision

---

**3. API Endpoints**
- Location: New file `app/routes/proxy.py`
- Endpoints needed:

**GET `/api/proxy/list`**
- Returns: List of all configured proxies with health status
- Response includes: id, proxy_url (masked), priority, enabled, health_status, response_time, statistics

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
- Triggers: Manual health check
- Updates: Database with result
- Returns: health status + response_time

**POST `/api/proxy/{proxy_id}/update-priority`**
- Parameters: priority (integer)
- Updates: Proxy priority
- Returns: success

---

**4. Model Updates**
- Location: Existing file `app/models.py`
- New model class: `ProxySettings`
- Updated model class: `RecordingSettings` (add proxy config columns)

---

**5. Application Startup**
- Location: Existing file `app/main.py`
- Changes needed:
  - Register proxy routes
  - Start ProxyHealthService on app startup
  - Stop ProxyHealthService on app shutdown

---

### Frontend Components Needed

**1. ProxySettingsPanel Component**
- Location: New file `app/frontend/src/components/settings/ProxySettingsPanel.vue`
- Displayed in: Settings View (new tab or section)

**UI Elements:**

**System Status Header:**
- Shows overall proxy system status
- Possible states:
  - ✅ HEALTHY: "X of Y proxies healthy"
  - ⚠️ DEGRADED: "All proxies down - using direct connection fallback"
  - ❌ ERROR: "All proxies down - recordings will fail"
  - 🔌 DISABLED: "Proxy system disabled - using direct connection"

**Proxy List:**
- Table/Cards showing all configured proxies
- Columns:
  - Proxy URL (masked: `http://user:***@host:port`)
  - Priority (0, 1, 2, etc.)
  - Health Status Badge (✅/⚠️/❌/❓)
  - Response Time (e.g., "123ms" or "Timeout")
  - Last Check Time (e.g., "2 minutes ago")
  - Consecutive Failures Count
  - Actions: Test, Enable/Disable, Delete

**Add Proxy Button:**
- Opens dialog/modal
- Input: Proxy URL (text field)
- Input: Priority (number field, default 0)
- Validation: URL must start with http:// or https://
- Action: Creates proxy + triggers health check
- Shows: Success/error toast

**Advanced Settings (Collapsible):**
- Enable Proxy System (toggle)
- Health Check Interval (number input, minutes)
- Max Consecutive Failures (number input, 1-10)
- Fallback to Direct Connection (toggle)

---

**2. Composable**
- Location: New file `app/frontend/src/composables/useProxySettings.ts`
- Purpose: Manage proxy settings state and API calls

**State:**
- `proxies` - List of proxy objects
- `config` - Proxy configuration (enable_proxy, health_check_interval, etc.)
- `isLoading` - Loading state
- `error` - Error message

**Computed:**
- `healthyProxyCount` - Number of healthy enabled proxies
- `proxySystemStatus` - Overall system status object

**Methods:**
- `fetchProxies()` - Load all proxies from API
- `addProxy(url, priority)` - Add new proxy
- `deleteProxy(id)` - Remove proxy
- `toggleProxy(id)` - Enable/disable proxy
- `testProxy(id)` - Manual health check
- `updatePriority(id, priority)` - Change priority

**WebSocket Listener:**
- Subscribe to `proxy_health_update` events
- Update proxy list in real-time

---

**3. TypeScript Types**
- Location: New file `app/frontend/src/types/proxy.ts`
- Interfaces needed:
  - `ProxySettings` - Proxy object structure
  - `ProxyHealthCheckResult` - Health check result
  - `ProxyConfigSettings` - Configuration options

---

## 📂 Files to Create

**Backend:**
1. `migrations/025_add_multi_proxy_support.py` - Database migration
2. `app/services/proxy/__init__.py` - Package init file
3. `app/services/proxy/proxy_health_service.py` - Health check service
4. `app/routes/proxy.py` - API endpoints

**Frontend:**
1. `app/frontend/src/types/proxy.ts` - TypeScript interfaces
2. `app/frontend/src/composables/useProxySettings.ts` - Proxy composable
3. `app/frontend/src/components/settings/ProxySettingsPanel.vue` - UI component

---

## 📂 Files to Modify

**Backend:**
1. `app/models.py` - Add ProxySettings model + RecordingSettings columns
2. `app/services/recording/process_manager.py` - Use proxy selection instead of hardcoded
3. `app/main.py` - Register routes + start/stop health service

**Frontend:**
1. `app/frontend/src/views/SettingsView.vue` - Add ProxySettingsPanel tab

---

## ✅ Acceptance Criteria

### Database
- [ ] `proxy_settings` table exists with all required columns
- [ ] Indexes created on enabled, health_status, priority
- [ ] Existing proxy migrated from global_settings (if exists)
- [ ] `recording_settings` has new proxy config columns

### Backend Service
- [ ] ProxyHealthService singleton created
- [ ] Health check tests proxy connectivity via Twitch API
- [ ] Response time measured in milliseconds
- [ ] Health status categorized correctly (healthy/degraded/failed)
- [ ] Periodic health checks run every 5 minutes
- [ ] Proxies auto-disable after 3 consecutive failures
- [ ] Best proxy selection algorithm works (healthy > degraded, sorted by priority + response time)
- [ ] Fallback to direct connection works when all proxies fail
- [ ] WebSocket broadcasts health updates

### API Endpoints
- [ ] GET /api/proxy/list returns all proxies with status
- [ ] POST /api/proxy/add creates new proxy
- [ ] DELETE /api/proxy/{id} removes proxy
- [ ] POST /api/proxy/{id}/toggle enables/disables proxy
- [ ] POST /api/proxy/{id}/test triggers manual health check
- [ ] POST /api/proxy/{id}/update-priority changes priority
- [ ] Password masking works in API responses

### Process Manager Integration
- [ ] ProcessManager calls get_best_proxy() before starting recording
- [ ] Checks if proxy enabled in settings
- [ ] Uses returned proxy for Streamlink command
- [ ] Falls back to direct connection if all proxies fail
- [ ] Logs proxy selection decisions

### Frontend UI
- [ ] ProxySettingsPanel displays system status indicator
- [ ] Proxy list shows all configured proxies
- [ ] Health badges display correctly (✅/⚠️/❌/❓)
- [ ] Add Proxy dialog works
- [ ] Test button triggers manual health check
- [ ] Enable/Disable toggle works
- [ ] Delete button removes proxy
- [ ] Priority ordering visible and modifiable
- [ ] Real-time WebSocket updates reflected in UI
- [ ] Advanced settings section works (enable proxy, intervals, fallback)

### Integration
- [ ] Recording starts with best available healthy proxy
- [ ] Recording falls back to direct connection when all proxies fail
- [ ] Recording fails gracefully if fallback disabled and no proxies available
- [ ] WebSocket broadcasts proxy status changes
- [ ] Frontend shows real-time proxy health updates

---

## 🧪 Testing Checklist

### Manual Testing Scenarios

**1. Basic Proxy Management**
- [ ] Add 3 proxies via UI (with different priorities)
- [ ] Verify proxies appear in list with "unknown" status
- [ ] Click "Test" on each proxy → Status updates
- [ ] Toggle proxy enabled/disabled → State changes
- [ ] Delete proxy → Removed from list
- [ ] Change proxy priority → Order updates

**2. Health Check System**
- [ ] Wait 5 minutes → Verify automatic health check runs
- [ ] Check logs for health check messages
- [ ] Verify database updated (last_health_check, health_status, response_time)
- [ ] Verify WebSocket messages sent to frontend
- [ ] Verify UI updates automatically

**3. Auto-Disable Feature**
- [ ] Manually set proxy to 3 consecutive failures (database)
- [ ] Wait for next health check OR trigger manual test
- [ ] Verify proxy auto-disabled
- [ ] Check logs for "auto-disabled" message
- [ ] Verify WebSocket notification sent

**4. Proxy Selection Algorithm**
- [ ] Add proxies: 1 healthy (priority 0), 1 degraded (priority 1), 1 failed (priority 2)
- [ ] Start recording → Check logs for proxy selection
- [ ] Verify healthy proxy (priority 0) selected
- [ ] Disable healthy proxy → Verify degraded proxy selected next
- [ ] Disable all proxies → Verify direct connection used (if fallback enabled)

**5. Recording Integration**
- [ ] Add streamer, wait for stream.online event
- [ ] Check logs for "Using proxy: ..." message
- [ ] Verify Streamlink command includes --http-proxy argument
- [ ] Verify recording works with proxy
- [ ] Simulate proxy failure mid-recording → Check error handling

**6. Fallback to Direct Connection**
- [ ] Disable all proxies OR mark all as failed
- [ ] Enable fallback in settings
- [ ] Start recording → Verify direct connection used
- [ ] Check logs for "No healthy proxies - using direct connection" message

**7. WebSocket Updates**
- [ ] Open Settings → Proxy panel
- [ ] Trigger health check (manual or wait 5 min)
- [ ] Verify UI updates without page refresh
- [ ] Check browser console for WebSocket messages

**8. Edge Cases**
- [ ] No proxies configured → System uses direct connection
- [ ] All proxies disabled → Fallback to direct or error
- [ ] Fallback disabled + all proxies failed → Recording should fail gracefully
- [ ] Proxy with invalid URL → Validation error on add
- [ ] Duplicate proxy URL → Error message

---

## 📖 Documentation References

**Primary Documentation:**
- `docs/BACKEND_FEATURES_PLANNED.md` (Section 2) - Detailed technical implementation notes
- `docs/MASTER_TASK_LIST.md` (Task #3) - High-level overview and progress tracking

**Related Documentation:**
- `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md` - Frontend design patterns
- `docs/DESIGN_SYSTEM.md` - UI component styling reference

**Relevant Code Files:**
- `app/utils/streamlink_utils.py` - Current proxy implementation (single proxy)
- `app/services/recording/process_manager.py` - Where proxy is used for recordings
- `app/models.py` - Current GlobalSettings model with http_proxy column

---

## 🚨 Security Considerations

**⚠️ CRITICAL: Proxy Credentials**

Proxy URLs contain sensitive credentials (username, password):
- Example: `http://username:password@proxy-host:9999`

**Security Measures:**

**1. Password Masking in API Responses**
- Never return full proxy URL with password in API responses
- Mask password: `http://username:***@proxy-host:9999`
- Only show full URL when editing (in input field)

**2. Password Masking in Logs**
- Truncate proxy URLs in log messages
- Example: `logger.info(f"Using proxy: {proxy_url[:50]}...")`
- Never log full proxy URL with credentials

**3. Database Security**
- Proxy credentials stored in database (consider encryption in future)
- Database access already secured by application layer
- Future enhancement: Encrypt proxy_url column

**4. Frontend Display**
- Mask passwords in UI table/list
- Show full URL only in edit dialog (when user needs to update)
- Use input type="password" for password field when adding proxy

---

## 🎯 Success Criteria

**Definition of Done:**
- [ ] Migration 025 completed successfully
- [ ] ProxySettings model exists in database
- [ ] ProxyHealthService implemented with all methods
- [ ] Background health checks run every 5 minutes
- [ ] Proxies auto-disable after 3 consecutive failures
- [ ] ProcessManager uses best available proxy for recordings
- [ ] Fallback to direct connection works
- [ ] All API endpoints functional and tested
- [ ] Frontend ProxySettingsPanel fully functional
- [ ] WebSocket updates work in real-time
- [ ] Recording starts with healthy proxy
- [ ] All acceptance criteria met
- [ ] Manual testing completed
- [ ] No sensitive data exposed in logs or API

**Known Limitations:**
- Cannot switch proxy mid-recording (Streamlink limitation - requires process restart)
- Health checks run every 5 minutes (not real-time)
- Proxy credentials stored unencrypted in database (acceptable for v1, encrypt in future)

**Future Enhancements (Not in Scope):**
- Mid-recording proxy recovery (complex, requires Streamlink process management)
- Proxy credential encryption at rest
- Geographic proxy location tracking
- Proxy bandwidth usage monitoring
- Per-streamer proxy assignment

---

**End of Issue #2 Documentation**

*Priority: CRITICAL - Implement as Sprint 1 Hotfix to restore recording functionality*

#### Migration 025: `proxy_settings` Table

**File:** `migrations/025_add_multi_proxy_support.py` (NEW)

**Schema Design:**
```sql
CREATE TABLE proxy_settings (
    id SERIAL PRIMARY KEY,
    proxy_url VARCHAR(500) NOT NULL,  -- http://user:pass@host:port
    priority INTEGER DEFAULT 0,        -- Lower = higher priority (0 = highest)
    enabled BOOLEAN DEFAULT TRUE,
    
    -- Health Check Data
    last_health_check TIMESTAMP WITH TIME ZONE,
    health_status VARCHAR(20),         -- healthy, degraded, failed, unknown
    consecutive_failures INTEGER DEFAULT 0,
    average_response_time_ms INTEGER,
    
    -- Statistics
    total_recordings INTEGER DEFAULT 0,
    failed_recordings INTEGER DEFAULT 0,
    success_rate FLOAT,                -- (total - failed) / total
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_proxy_enabled ON proxy_settings(enabled);
CREATE INDEX idx_proxy_health ON proxy_settings(health_status);
CREATE INDEX idx_proxy_priority ON proxy_settings(priority);
```

**Migration Code:**
```python
#!/usr/bin/env python
"""
Migration 025: Add multi-proxy support
Creates proxy_settings table and migrates existing proxy from global_settings
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Create proxy_settings table and migrate existing proxy"""
    session = None
    try:
        engine = create_engine(settings.DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        logger.info("🔄 Creating proxy_settings table...")
        
        # Create proxy_settings table
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS proxy_settings (
                id SERIAL PRIMARY KEY,
                proxy_url VARCHAR(500) NOT NULL,
                priority INTEGER DEFAULT 0,
                enabled BOOLEAN DEFAULT TRUE,
                
                last_health_check TIMESTAMP WITH TIME ZONE,
                health_status VARCHAR(20) DEFAULT 'unknown',
                consecutive_failures INTEGER DEFAULT 0,
                average_response_time_ms INTEGER,
                
                total_recordings INTEGER DEFAULT 0,
                failed_recordings INTEGER DEFAULT 0,
                success_rate FLOAT,
                
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        logger.info("✅ Created proxy_settings table")
        
        # Create indexes
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_proxy_enabled 
            ON proxy_settings(enabled)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_proxy_health 
            ON proxy_settings(health_status)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_proxy_priority 
            ON proxy_settings(priority)
        """))
        logger.info("✅ Created indexes")
        
        # Migrate existing proxy from global_settings
        result = session.execute(text("""
            SELECT http_proxy FROM global_settings 
            WHERE http_proxy IS NOT NULL AND http_proxy != '' 
            LIMIT 1
        """))
        existing_proxy = result.scalar()
        
        if existing_proxy:
            logger.info(f"🔄 Migrating existing proxy: {existing_proxy[:50]}...")
            
            # Insert as priority 0 (highest)
            session.execute(text("""
                INSERT INTO proxy_settings (proxy_url, priority, enabled, health_status)
                VALUES (:proxy_url, 0, TRUE, 'unknown')
            """), {"proxy_url": existing_proxy})
            
            logger.info("✅ Migrated existing proxy")
        else:
            logger.info("ℹ️ No existing proxy found to migrate")
        
        # Add new columns to recording_settings
        logger.info("🔄 Adding proxy configuration to recording_settings...")
        
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS enable_proxy BOOLEAN DEFAULT TRUE
        """))
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS proxy_health_check_enabled BOOLEAN DEFAULT TRUE
        """))
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS proxy_health_check_interval_seconds INTEGER DEFAULT 300
        """))
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS proxy_max_consecutive_failures INTEGER DEFAULT 3
        """))
        session.execute(text("""
            ALTER TABLE recording_settings 
            ADD COLUMN IF NOT EXISTS fallback_to_direct_connection BOOLEAN DEFAULT TRUE
        """))
        
        logger.info("✅ Added proxy configuration columns")
        
        session.commit()
        logger.info("🎉 Migration 025 completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Migration 025 failed: {e}")
        if session:
            session.rollback()
        raise
    finally:
        if session and session.is_active:
            session.close()

if __name__ == "__main__":
    run_migration()
```

**Testing Migration:**
```bash
# Run migration
cd migrations
python 025_add_multi_proxy_support.py

# Verify table created
psql $DATABASE_URL -c "\d proxy_settings"

# Verify existing proxy migrated
psql $DATABASE_URL -c "SELECT * FROM proxy_settings;"

# Expected output:
# id | proxy_url                      | priority | enabled | health_status
# 1  | http://serph91p:***@77.90...   | 0        | true    | unknown
```

---

### Phase 2: Backend Service (60-90 minutes)

#### ProxyHealthService (NEW)

**File:** `app/services/proxy/proxy_health_service.py` (NEW)

**Complete Implementation:**
```python
"""
Proxy Health Service for StreamVault

Manages proxy health checks, selection, and automatic failover.
Runs periodic health checks and provides best proxy selection.
"""

import asyncio
import time
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ProxySettings
from app.config.constants import TIMEOUTS, RETRY_CONFIG

logger = logging.getLogger(__name__)

class ProxyHealthService:
    """
    Service for managing proxy health checks and selection
    
    Features:
    - Periodic health checks (every 5 minutes)
    - Connectivity testing via Twitch API
    - Response time measurement
    - Auto-disable after consecutive failures
    - Best proxy selection algorithm
    """
    
    def __init__(self):
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def check_proxy_health(self, proxy_url: str) -> Dict[str, Any]:
        """
        Test proxy connectivity and measure response time
        
        Args:
            proxy_url: Full proxy URL (http://user:pass@host:port)
        
        Returns:
            {
                "status": "healthy" | "degraded" | "failed",
                "response_time_ms": 123,
                "error": "error message if failed"
            }
        """
        start_time = time.time()
        
        try:
            # Test with Twitch API endpoint (small, fast, reliable)
            async with httpx.AsyncClient(
                proxies={
                    "http://": proxy_url,
                    "https://": proxy_url
                },
                timeout=10.0,
                follow_redirects=True
            ) as client:
                # Use Twitch API health check endpoint
                response = await client.get(
                    "https://api.twitch.tv/helix/streams",
                    headers={"Client-ID": "your-client-id"}  # Use app client ID
                )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Determine health status based on HTTP status code
            if response.status_code == 200:
                logger.debug(f"✅ Proxy health check passed: {proxy_url[:50]}... ({response_time_ms}ms)")
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms
                }
            elif response.status_code < 500:
                # Client errors (4xx) - proxy works but request invalid
                logger.warning(f"⚠️ Proxy degraded: {proxy_url[:50]}... - HTTP {response.status_code}")
                return {
                    "status": "degraded",
                    "response_time_ms": response_time_ms,
                    "error": f"HTTP {response.status_code}"
                }
            else:
                # Server errors (5xx) - proxy or upstream failed
                logger.error(f"❌ Proxy failed: {proxy_url[:50]}... - HTTP {response.status_code}")
                return {
                    "status": "failed",
                    "response_time_ms": response_time_ms,
                    "error": f"HTTP {response.status_code}"
                }
                
        except asyncio.TimeoutError:
            response_time_ms = 10000  # Timeout after 10s
            logger.error(f"❌ Proxy timeout: {proxy_url[:50]}... (>10s)")
            return {
                "status": "failed",
                "response_time_ms": response_time_ms,
                "error": "Timeout (>10s)"
            }
        except httpx.ProxyError as e:
            logger.error(f"❌ Proxy connection error: {proxy_url[:50]}... - {e}")
            return {
                "status": "failed",
                "response_time_ms": 0,
                "error": f"Proxy error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Proxy health check failed: {proxy_url[:50]}... - {e}")
            return {
                "status": "failed",
                "response_time_ms": 0,
                "error": str(e)
            }
    
    async def get_best_proxy(self) -> Optional[str]:
        """
        Select best available proxy based on health status
        
        Selection Algorithm:
        1. Filter enabled proxies
        2. Prioritize by health_status: healthy > degraded > failed
        3. Sort by priority (ascending, 0 = highest)
        4. Sort by average_response_time_ms (ascending, faster = better)
        5. Return first match
        
        Returns:
            Proxy URL string or None if no healthy proxies available
        """
        with SessionLocal() as db:
            proxies = db.query(ProxySettings).filter(
                ProxySettings.enabled == True
            ).order_by(
                ProxySettings.priority.asc(),
                ProxySettings.average_response_time_ms.asc()
            ).all()
            
            if not proxies:
                logger.warning("⚠️ No proxies configured")
                return None
            
            # Filter by health status
            healthy = [p for p in proxies if p.health_status == "healthy"]
            degraded = [p for p in proxies if p.health_status == "degraded"]
            
            if healthy:
                best = healthy[0]
                logger.info(f"✅ Selected healthy proxy: {best.proxy_url[:50]}... (priority={best.priority}, {best.average_response_time_ms}ms)")
                return best.proxy_url
            elif degraded:
                best = degraded[0]
                logger.warning(f"⚠️ No healthy proxies - using degraded proxy: {best.proxy_url[:50]}...")
                return best.proxy_url
            else:
                logger.error("🚨 All proxies failed health checks")
                return None
    
    async def run_health_checks(self):
        """
        Periodic health check task (runs every 5 minutes)
        
        This is a long-running background task that:
        1. Queries all enabled proxies
        2. Tests each proxy connectivity
        3. Updates health status in database
        4. Auto-disables proxies after consecutive failures
        5. Broadcasts status updates via WebSocket
        """
        from app.services.communication.websocket_manager import websocket_manager
        
        logger.info("🔍 Starting proxy health check service (interval: 5 minutes)")
        self._running = True
        
        while self._running:
            try:
                with SessionLocal() as db:
                    proxies = db.query(ProxySettings).filter(
                        ProxySettings.enabled == True
                    ).all()
                    
                    if not proxies:
                        logger.debug("No proxies to check")
                        await asyncio.sleep(300)
                        continue
                    
                    logger.info(f"🔍 Running health checks for {len(proxies)} proxies...")
                    
                    for proxy in proxies:
                        # Test proxy health
                        health = await self.check_proxy_health(proxy.proxy_url)
                        
                        # Update database
                        proxy.last_health_check = datetime.now(timezone.utc)
                        proxy.health_status = health["status"]
                        proxy.average_response_time_ms = health.get("response_time_ms", 0)
                        
                        # Track consecutive failures
                        if health["status"] == "failed":
                            proxy.consecutive_failures += 1
                            logger.warning(f"⚠️ Proxy failure #{proxy.consecutive_failures}: {proxy.proxy_url[:50]}...")
                        else:
                            # Reset counter on success
                            proxy.consecutive_failures = 0
                        
                        # Auto-disable after too many failures
                        if proxy.consecutive_failures >= 3:
                            proxy.enabled = False
                            logger.error(f"🚨 Proxy auto-disabled after 3 consecutive failures: {proxy.proxy_url[:50]}...")
                            
                            # Send critical notification
                            await websocket_manager.broadcast({
                                "type": "proxy_disabled",
                                "proxy_id": proxy.id,
                                "proxy_url": proxy.proxy_url[:50] + "...",
                                "reason": "3 consecutive failures"
                            })
                        
                        db.commit()
                        
                        # Broadcast health update
                        await websocket_manager.broadcast({
                            "type": "proxy_health_update",
                            "proxy": {
                                "id": proxy.id,
                                "health_status": proxy.health_status,
                                "response_time_ms": proxy.average_response_time_ms,
                                "consecutive_failures": proxy.consecutive_failures
                            }
                        })
                        
                        logger.info(f"🔍 Proxy health: {proxy.proxy_url[:50]}... - {health['status']} ({health.get('response_time_ms', 0)}ms)")
                
            except Exception as e:
                logger.error(f"❌ Health check loop failed: {e}", exc_info=True)
            
            # Wait 5 minutes before next check
            await asyncio.sleep(300)
    
    def start(self):
        """Start health check background task"""
        if not self._health_check_task or self._health_check_task.done():
            self._health_check_task = asyncio.create_task(self.run_health_checks())
            logger.info("✅ Proxy health check service started")
    
    def stop(self):
        """Stop health check background task"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            logger.info("⏹️ Proxy health check service stopped")

# Singleton instance
_proxy_health_service: Optional[ProxyHealthService] = None

def get_proxy_health_service() -> ProxyHealthService:
    """Get singleton instance of ProxyHealthService"""
    global _proxy_health_service
    if _proxy_health_service is None:
        _proxy_health_service = ProxyHealthService()
    return _proxy_health_service
```

**Testing ProxyHealthService:**
```python
# Test health check
import asyncio
from app.services.proxy.proxy_health_service import ProxyHealthService

async def test():
    service = ProxyHealthService()
    
    # Test specific proxy
    result = await service.check_proxy_health("http://proxy:9999")
    print(f"Health: {result}")
    
    # Get best proxy
    best = await service.get_best_proxy()
    print(f"Best proxy: {best}")

asyncio.run(test())
```

---

### Phase 3: Process Manager Integration (30 minutes)

**File:** `migrations/025_add_multi_proxy_support.py`

```python
def upgrade():
    # Create proxy_settings table
    op.create_table(
        'proxy_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('proxy_url', sa.String(), nullable=False),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('enabled', sa.Boolean(), default=True),
        
        # Health check data
        sa.Column('last_health_check', sa.DateTime(timezone=True)),
        sa.Column('health_status', sa.String()),  # healthy/degraded/failed
        sa.Column('consecutive_failures', sa.Integer(), default=0),
        sa.Column('average_response_time_ms', sa.Integer()),
        
        # Statistics
        sa.Column('total_recordings', sa.Integer(), default=0),
        sa.Column('failed_recordings', sa.Integer(), default=0),
        sa.Column('success_rate', sa.Float())
    )
    
    # Update RecordingSettings
    op.add_column('recording_settings', 
        sa.Column('enable_proxy', sa.Boolean(), default=True))
    op.add_column('recording_settings',
        sa.Column('proxy_health_check_enabled', sa.Boolean(), default=True))
    op.add_column('recording_settings',
        sa.Column('proxy_health_check_interval_seconds', sa.Integer(), default=300))
    op.add_column('recording_settings',
        sa.Column('proxy_max_consecutive_failures', sa.Integer(), default=3))
    op.add_column('recording_settings',
        sa.Column('fallback_to_direct_connection', sa.Boolean(), default=True))
    
    # Migrate existing proxy
    connection = op.get_bind()
    result = connection.execute(
        "SELECT proxy FROM recording_settings WHERE proxy IS NOT NULL LIMIT 1"
    )
    existing_proxy = result.scalar()
    
    if existing_proxy:
        connection.execute(
            f"INSERT INTO proxy_settings (proxy_url, priority, enabled) "
            f"VALUES ('{existing_proxy}', 0, TRUE)"
        )
```

---

#### 2. ProxyHealthService (60-90min)

**File:** `app/services/proxy/proxy_health_service.py` (NEW)

```python
import asyncio
import time
import httpx
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import ProxySettings

class ProxyHealthService:
    """Manages proxy health checks and selection"""
    
    async def check_proxy_health(self, proxy_url: str) -> dict:
        """
        Test proxy connectivity
        
        Returns:
            {
                "status": "healthy" | "degraded" | "failed",
                "response_time_ms": 123,
                "error": "error message if failed"
            }
        """
        start_time = time.time()
        
        try:
            # Test with Twitch API endpoint (small, fast)
            async with httpx.AsyncClient(
                proxies={"http://": proxy_url, "https://": proxy_url},
                timeout=10.0
            ) as client:
                response = await client.get("https://api.twitch.tv/helix/streams")
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time_ms
                }
            elif response.status_code < 500:
                return {
                    "status": "degraded",
                    "response_time_ms": response_time_ms,
                    "error": f"HTTP {response.status_code}"
                }
            else:
                return {
                    "status": "failed",
                    "response_time_ms": response_time_ms,
                    "error": f"HTTP {response.status_code}"
                }
                
        except asyncio.TimeoutError:
            return {
                "status": "failed",
                "response_time_ms": 10000,
                "error": "Timeout (>10s)"
            }
        except Exception as e:
            return {
                "status": "failed",
                "response_time_ms": 0,
                "error": str(e)
            }
    
    async def get_best_proxy(self) -> Optional[str]:
        """
        Select best available proxy based on health status
        
        Priority:
        1. Healthy proxies with lowest response time
        2. Degraded proxies (if no healthy ones)
        3. None (direct connection if fallback enabled)
        """
        with SessionLocal() as db:
            proxies = db.query(ProxySettings).filter(
                ProxySettings.enabled == True
            ).order_by(
                ProxySettings.priority.asc(),
                ProxySettings.average_response_time_ms.asc()
            ).all()
            
            # Filter by health status
            healthy = [p for p in proxies if p.health_status == "healthy"]
            degraded = [p for p in proxies if p.health_status == "degraded"]
            
            if healthy:
                return healthy[0].proxy_url
            elif degraded:
                logger.warning("⚠️ No healthy proxies available, using degraded proxy")
                return degraded[0].proxy_url
            else:
                logger.error("🚨 All proxies failed health checks")
                return None
    
    async def run_health_checks(self):
        """Periodic health check task (runs every 5 minutes)"""
        while True:
            try:
                with SessionLocal() as db:
                    proxies = db.query(ProxySettings).filter(
                        ProxySettings.enabled == True
                    ).all()
                    
                    for proxy in proxies:
                        health = await self.check_proxy_health(proxy.proxy_url)
                        
                        proxy.last_health_check = datetime.now(timezone.utc)
                        proxy.health_status = health["status"]
                        proxy.average_response_time_ms = health.get("response_time_ms", 0)
                        
                        if health["status"] == "failed":
                            proxy.consecutive_failures += 1
                        else:
                            proxy.consecutive_failures = 0
                        
                        # Auto-disable after too many failures
                        if proxy.consecutive_failures >= 3:
                            proxy.enabled = False
                            logger.error(f"🚨 Proxy {proxy.proxy_url} disabled after 3 consecutive failures")
                        
                        db.commit()
                        
                        logger.info(f"🔍 Proxy health: {proxy.proxy_url} - {health['status']} ({health.get('response_time_ms', 0)}ms)")
                
            except Exception as e:
                logger.error(f"Health check failed: {e}")
            
            # Wait 5 minutes before next check
            await asyncio.sleep(300)
```

---

#### 3. ProcessManager Update (30min)

**File:** `app/services/recording/process_manager.py`

```python
async def _build_streamlink_command(self, ...):
    # Get best available proxy
    proxy_url = None
    
    if recording_settings.enable_proxy:
        from app.services.proxy.proxy_health_service import ProxyHealthService
        proxy_service = ProxyHealthService()
        
        proxy_url = await proxy_service.get_best_proxy()
        
        if proxy_url:
            logger.info(f"🔗 Using proxy: {proxy_url}")
            command.extend(["--http-proxy", proxy_url])
        elif recording_settings.fallback_to_direct_connection:
            logger.warning("⚠️ No healthy proxies - using direct connection")
        else:
            raise Exception("No healthy proxies available and direct connection disabled")
    else:
        logger.info("🔗 Proxy disabled - using direct connection")
```

---

#### 4. API Endpoints (30-45min)

**File:** `app/routes/proxy.py` (NEW)

```python
from fastapi import APIRouter, HTTPException
from app.database import SessionLocal
from app.models import ProxySettings
from app.services.proxy.proxy_health_service import ProxyHealthService

router = APIRouter()

@router.get("/api/proxy/list")
async def get_proxies():
    """Get all configured proxies with health status"""
    with SessionLocal() as db:
        proxies = db.query(ProxySettings).all()
        return {
            "proxies": [
                {
                    "id": p.id,
                    "proxy_url": mask_password(p.proxy_url),
                    "priority": p.priority,
                    "enabled": p.enabled,
                    "health_status": p.health_status,
                    "last_health_check": p.last_health_check,
                    "average_response_time_ms": p.average_response_time_ms,
                    "consecutive_failures": p.consecutive_failures,
                    "success_rate": p.success_rate
                }
                for p in proxies
            ]
        }

@router.post("/api/proxy/add")
async def add_proxy(proxy_url: str, priority: int = 0):
    """Add new proxy"""
    if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
        raise HTTPException(400, "Proxy URL must start with http:// or https://")
    
    with SessionLocal() as db:
        proxy = ProxySettings(
            proxy_url=proxy_url,
            priority=priority,
            enabled=True,
            health_status="unknown"
        )
        db.add(proxy)
        db.commit()
        
        # Trigger immediate health check
        health_service = ProxyHealthService()
        await health_service.check_proxy_health(proxy_url)
        
        return {"success": True, "proxy_id": proxy.id}

@router.post("/api/proxy/{proxy_id}/test")
async def test_proxy(proxy_id: int):
    """Manually test proxy connectivity"""
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        health_service = ProxyHealthService()
        result = await health_service.check_proxy_health(proxy.proxy_url)
        
        # Update database
        proxy.last_health_check = datetime.now(timezone.utc)
        proxy.health_status = result["status"]
        proxy.average_response_time_ms = result.get("response_time_ms", 0)
        db.commit()
        
        return result

@router.delete("/api/proxy/{proxy_id}")
async def delete_proxy(proxy_id: int):
    """Delete proxy"""
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        db.delete(proxy)
        db.commit()
        
        return {"success": True}

@router.post("/api/proxy/{proxy_id}/toggle")
async def toggle_proxy(proxy_id: int):
    """Enable/Disable proxy"""
    with SessionLocal() as db:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        proxy.enabled = not proxy.enabled
        db.commit()
        
        return {"success": True, "enabled": proxy.enabled}
```

---

### Frontend (1 hour)

#### 1. ProxySettingsPanel Component (45min)

**File:** `app/frontend/src/components/settings/ProxySettingsPanel.vue` (NEW)

See detailed implementation in `docs/BACKEND_FEATURES_PLANNED.md` Section 2.

**Key Features:**
- System status header (healthy/degraded/error/disabled)
- Proxy list with health badges
- Add/Remove/Test/Toggle buttons
- Advanced settings (health check interval, max failures, fallback)
- Real-time WebSocket updates

---

#### 2. Composable (15min)

**File:** `app/frontend/src/composables/useProxySettings.ts` (NEW)

```typescript
export function useProxySettings() {
  const proxies = ref<ProxySettings[]>([])
  const config = ref<ProxyConfigSettings>({...})
  
  const healthyProxyCount = computed(...)
  const proxySystemStatus = computed(...)
  
  async function fetchProxies() {...}
  async function addProxy(url, priority) {...}
  async function testProxy(id) {...}
  async function toggleProxy(id) {...}
  
  // WebSocket listener
  subscribe('proxy_health_update', (data) => {...})
  
  return {
    proxies,
    config,
    healthyProxyCount,
    proxySystemStatus,
    addProxy,
    testProxy,
    toggleProxy
  }
}
```

---

### Phase 3: Process Manager Integration (30 minutes)

#### Update `process_manager.py`

**File:** `app/services/recording/process_manager.py`

**Current Implementation (line 171-212):**
```python
# Get proxy settings and codec preferences from database
proxy_settings = get_proxy_settings_from_db()  # OLD: Single proxy

# CRITICAL: Check proxy connectivity before starting recording
if proxy_settings and any(proxy_settings.values()):
    from app.utils.streamlink_utils import check_proxy_connectivity
    
    is_reachable, proxy_error = check_proxy_connectivity(proxy_settings)
    
    if not is_reachable:
        error_msg = f"Cannot start recording for {streamer_name}: Proxy connection failed - {proxy_error}"
        logger.error(f"🔴 PROXY_DOWN: {error_msg}")
        raise ProcessError(f"Proxy connection failed: {proxy_error}")
```

**New Implementation:**
```python
# Get best available proxy from health service
proxy_url = None

# Check if proxy is enabled in recording settings
from app.database import SessionLocal
with SessionLocal() as db:
    recording_settings = db.query(RecordingSettings).first()
    
    if recording_settings and recording_settings.enable_proxy:
        # Use proxy rotation system
        from app.services.proxy.proxy_health_service import get_proxy_health_service
        proxy_service = get_proxy_health_service()
        
        proxy_url = await proxy_service.get_best_proxy()
        
        if proxy_url:
            logger.info(f"🔗 Using proxy: {proxy_url[:50]}...")
            proxy_settings = {"http": proxy_url, "https": proxy_url}
            
            # Still check connectivity before starting
            from app.utils.streamlink_utils import check_proxy_connectivity
            is_reachable, proxy_error = check_proxy_connectivity(proxy_settings)
            
            if not is_reachable:
                logger.error(f"🔴 Selected proxy failed connectivity check: {proxy_error}")
                proxy_url = None  # Fallback to direct connection
        
        # Handle case when no healthy proxies available
        if not proxy_url:
            if recording_settings.fallback_to_direct_connection:
                logger.warning("⚠️ No healthy proxies available - using direct connection")
                proxy_settings = {}
            else:
                error_msg = f"Cannot start recording for {streamer_name}: No healthy proxies available and direct connection disabled"
                logger.error(f"🚨 {error_msg}")
                raise ProcessError(error_msg)
    else:
        logger.info("🔗 Proxy system disabled - using direct connection")
        proxy_settings = {}

# Generate streamlink command with proxy
cmd = get_streamlink_command(
    streamer_name=streamer_name,
    quality=quality,
    output_path=segment_path,
    proxy_settings=proxy_settings,
    supported_codecs=supported_codecs
)
```

**Changes Summary:**
- Replace `get_proxy_settings_from_db()` with `get_proxy_health_service().get_best_proxy()`
- Check `recording_settings.enable_proxy` flag
- Use fallback strategy if all proxies fail
- Still perform connectivity check before starting

---

### Phase 4: API Endpoints (30-45 minutes)

#### Proxy Management API

**File:** `app/routes/proxy.py` (NEW)

**Complete Implementation:**
```python
"""
Proxy Management API Routes

Endpoints for managing multiple proxies with health checks.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional

from app.database import get_db
from app.models import ProxySettings
from app.services.proxy.proxy_health_service import get_proxy_health_service

router = APIRouter()
logger = logging.getLogger(__name__)

def mask_password(url: str) -> str:
    """Mask password in proxy URL for display"""
    if "@" in url:
        # Split protocol://user:pass@host:port
        parts = url.split("@")
        if ":" in parts[0]:
            # Has user:pass
            protocol_user = parts[0].rsplit(":", 1)[0]  # protocol://user
            return f"{protocol_user}:***@{parts[1]}"
    return url

@router.get("/api/proxy/list")
async def get_proxies(db: Session = Depends(get_db)):
    """
    Get all configured proxies with health status
    
    Returns:
        {
            "proxies": [
                {
                    "id": 1,
                    "proxy_url": "http://user:***@host:port",
                    "priority": 0,
                    "enabled": true,
                    "health_status": "healthy",
                    "last_health_check": "2025-11-13T12:00:00Z",
                    "average_response_time_ms": 123,
                    "consecutive_failures": 0,
                    "success_rate": 0.95,
                    "total_recordings": 100,
                    "failed_recordings": 5
                }
            ]
        }
    """
    try:
        proxies = db.query(ProxySettings).order_by(
            ProxySettings.priority.asc()
        ).all()
        
        return {
            "proxies": [
                {
                    "id": p.id,
                    "proxy_url": mask_password(p.proxy_url),
                    "proxy_url_full": p.proxy_url,  # For editing (still sensitive!)
                    "priority": p.priority,
                    "enabled": p.enabled,
                    "health_status": p.health_status or "unknown",
                    "last_health_check": p.last_health_check.isoformat() if p.last_health_check else None,
                    "average_response_time_ms": p.average_response_time_ms,
                    "consecutive_failures": p.consecutive_failures,
                    "success_rate": p.success_rate,
                    "total_recordings": p.total_recordings or 0,
                    "failed_recordings": p.failed_recordings or 0
                }
                for p in proxies
            ]
        }
    except Exception as e:
        logger.error(f"Failed to fetch proxies: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch proxies: {str(e)}")

@router.post("/api/proxy/add")
async def add_proxy(
    proxy_url: str,
    priority: int = 0,
    db: Session = Depends(get_db)
):
    """
    Add new proxy
    
    Args:
        proxy_url: Full proxy URL (http://user:pass@host:port)
        priority: Priority (0 = highest, default)
    
    Returns:
        {"success": true, "proxy_id": 1}
    """
    try:
        # Validate proxy URL format
        if not proxy_url.startswith("http://") and not proxy_url.startswith("https://"):
            raise HTTPException(400, "Proxy URL must start with 'http://' or 'https://'")
        
        # Check for duplicates
        existing = db.query(ProxySettings).filter(
            ProxySettings.proxy_url == proxy_url
        ).first()
        
        if existing:
            raise HTTPException(400, "Proxy URL already exists")
        
        # Create new proxy
        proxy = ProxySettings(
            proxy_url=proxy_url,
            priority=priority,
            enabled=True,
            health_status="unknown",
            consecutive_failures=0
        )
        db.add(proxy)
        db.commit()
        db.refresh(proxy)
        
        logger.info(f"✅ Added proxy: {mask_password(proxy_url)} (priority={priority})")
        
        # Trigger immediate health check
        proxy_service = get_proxy_health_service()
        health = await proxy_service.check_proxy_health(proxy_url)
        
        # Update health status
        proxy.health_status = health["status"]
        proxy.average_response_time_ms = health.get("response_time_ms", 0)
        proxy.last_health_check = datetime.now(timezone.utc)
        db.commit()
        
        return {"success": True, "proxy_id": proxy.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add proxy: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to add proxy: {str(e)}")

@router.delete("/api/proxy/{proxy_id}")
async def delete_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """
    Delete proxy
    
    Args:
        proxy_id: Proxy ID to delete
    
    Returns:
        {"success": true}
    """
    try:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        logger.info(f"🗑️ Deleting proxy: {mask_password(proxy.proxy_url)}")
        
        db.delete(proxy)
        db.commit()
        
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete proxy: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to delete proxy: {str(e)}")

@router.post("/api/proxy/{proxy_id}/toggle")
async def toggle_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """
    Enable/Disable proxy
    
    Args:
        proxy_id: Proxy ID to toggle
    
    Returns:
        {"success": true, "enabled": true}
    """
    try:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        # Toggle enabled status
        proxy.enabled = not proxy.enabled
        
        # Reset consecutive failures when re-enabling
        if proxy.enabled:
            proxy.consecutive_failures = 0
        
        db.commit()
        
        status = "enabled" if proxy.enabled else "disabled"
        logger.info(f"✅ Proxy {status}: {mask_password(proxy.proxy_url)}")
        
        return {"success": True, "enabled": proxy.enabled}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle proxy: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to toggle proxy: {str(e)}")

@router.post("/api/proxy/{proxy_id}/test")
async def test_proxy(proxy_id: int, db: Session = Depends(get_db)):
    """
    Manually test proxy connectivity
    
    Args:
        proxy_id: Proxy ID to test
    
    Returns:
        {
            "status": "healthy" | "degraded" | "failed",
            "response_time_ms": 123,
            "error": "error message if failed"
        }
    """
    try:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        logger.info(f"🔍 Testing proxy: {mask_password(proxy.proxy_url)}")
        
        # Run health check
        proxy_service = get_proxy_health_service()
        result = await proxy_service.check_proxy_health(proxy.proxy_url)
        
        # Update database
        proxy.last_health_check = datetime.now(timezone.utc)
        proxy.health_status = result["status"]
        proxy.average_response_time_ms = result.get("response_time_ms", 0)
        db.commit()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test proxy: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to test proxy: {str(e)}")

@router.post("/api/proxy/{proxy_id}/update-priority")
async def update_proxy_priority(
    proxy_id: int,
    priority: int,
    db: Session = Depends(get_db)
):
    """
    Update proxy priority
    
    Args:
        proxy_id: Proxy ID
        priority: New priority (0 = highest)
    
    Returns:
        {"success": true}
    """
    try:
        proxy = db.query(ProxySettings).filter(ProxySettings.id == proxy_id).first()
        
        if not proxy:
            raise HTTPException(404, "Proxy not found")
        
        proxy.priority = priority
        db.commit()
        
        logger.info(f"✅ Updated proxy priority: {mask_password(proxy.proxy_url)} → {priority}")
        
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update proxy priority: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(500, f"Failed to update proxy priority: {str(e)}")
```

**Register Routes in `app/main.py`:**
```python
# Add proxy routes
from app.routes import proxy
app.include_router(proxy.router, tags=["proxy"])

# Start proxy health check service
from app.services.proxy.proxy_health_service import get_proxy_health_service

@app.on_event("startup")
async def startup_proxy_service():
    proxy_service = get_proxy_health_service()
    proxy_service.start()
    logger.info("✅ Proxy health check service started")

@app.on_event("shutdown")
async def shutdown_proxy_service():
    proxy_service = get_proxy_health_service()
    proxy_service.stop()
    logger.info("⏹️ Proxy health check service stopped")
```

---

### Phase 5: Update Models (15 minutes)

#### Add `ProxySettings` Model

**File:** `app/models.py`

**Insert after `GlobalSettings` class (around line 228):**
```python
class ProxySettings(Base):
    """
    Multi-proxy configuration with health tracking
    
    Enables automatic proxy failover and health monitoring.
    """
    __tablename__ = "proxy_settings"
    __table_args__ = (
        Index('idx_proxy_enabled', 'enabled'),
        Index('idx_proxy_health', 'health_status'),
        Index('idx_proxy_priority', 'priority'),
        {'extend_existing': True}
    )
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    proxy_url = Column(String(500), nullable=False)
    priority = Column(Integer, default=0)  # Lower = higher priority
    enabled = Column(Boolean, default=True)
    
    # Health Check Data
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), default="unknown")  # healthy, degraded, failed, unknown
    consecutive_failures = Column(Integer, default=0)
    average_response_time_ms = Column(Integer, nullable=True)
    
    # Statistics
    total_recordings = Column(Integer, default=0)
    failed_recordings = Column(Integer, default=0)
    success_rate = Column(Float, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

**Update `RecordingSettings` class:**
```python
class RecordingSettings(Base):
    __tablename__ = "recording_settings"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True)
    # ... existing fields ...
    
    # NEW: Proxy configuration (Migration 025)
    enable_proxy = Column(Boolean, default=True)
    proxy_health_check_enabled = Column(Boolean, default=True)
    proxy_health_check_interval_seconds = Column(Integer, default=300)  # 5 minutes
    proxy_max_consecutive_failures = Column(Integer, default=3)
    fallback_to_direct_connection = Column(Boolean, default=True)
```

---

## 📂 Files to Create

**Backend:**
- ✅ `migrations/025_add_multi_proxy_support.py` - Database schema
- ✅ `app/services/proxy/__init__.py` - Package init
- ✅ `app/services/proxy/proxy_health_service.py` - Health check service
- ✅ `app/routes/proxy.py` - API endpoints

**Frontend:**
- ⏳ `app/frontend/src/types/proxy.ts` - TypeScript interfaces
- ⏳ `app/frontend/src/composables/useProxySettings.ts` - Proxy composable
- ⏳ `app/frontend/src/components/settings/ProxySettingsPanel.vue` - UI component

---

## 📂 Files to Modify

**Backend:**
- ✅ `app/models.py` - Add ProxySettings model + RecordingSettings fields
- ✅ `app/services/recording/process_manager.py` - Use proxy rotation
- ✅ `app/main.py` - Register routes + start health check service

**Frontend:**
- ⏳ `app/frontend/src/views/SettingsView.vue` - Add ProxySettingsPanel

---

## ✅ Acceptance Criteria

### Backend

**Database:**
- [ ] Migration 025 runs successfully
- [ ] `proxy_settings` table created with all columns
- [ ] Existing proxy migrated from `global_settings.http_proxy`
- [ ] Indexes created (enabled, health_status, priority)

**Health Check Service:**
- [ ] ProxyHealthService singleton created
- [ ] `check_proxy_health()` tests connectivity via Twitch API
- [ ] Response time measured in milliseconds
- [ ] Health status determined: healthy/degraded/failed
- [ ] Periodic health checks run every 5 minutes
- [ ] Proxies auto-disabled after 3 consecutive failures
- [ ] WebSocket broadcasts health updates

**Proxy Selection:**
- [ ] `get_best_proxy()` returns best available proxy
- [ ] Selection prioritizes: healthy > degraded
- [ ] Sorting by priority (0 = highest) works
- [ ] Sorting by response_time_ms works
- [ ] Returns None if no healthy proxies

**Process Manager:**
- [ ] Uses `get_best_proxy()` instead of hardcoded proxy
- [ ] Checks `recording_settings.enable_proxy` flag
- [ ] Falls back to direct connection if all proxies fail
- [ ] Still performs connectivity check before starting
- [ ] Logs proxy selection decisions

**API Endpoints:**
- [ ] GET `/api/proxy/list` returns all proxies
- [ ] POST `/api/proxy/add` creates new proxy
- [ ] DELETE `/api/proxy/{id}` removes proxy
- [ ] POST `/api/proxy/{id}/toggle` enables/disables proxy
- [ ] POST `/api/proxy/{id}/test` triggers manual health check
- [ ] POST `/api/proxy/{id}/update-priority` changes priority
- [ ] Password masking works in responses

### Frontend

**ProxySettingsPanel:**
- [ ] System status indicator shows: healthy/degraded/error/disabled
- [ ] Proxy list displays all configured proxies
- [ ] Health badges show: ✅ healthy, ⚠️ degraded, ❌ failed, ❓ unknown
- [ ] "Add Proxy" button opens dialog
- [ ] "Test" button triggers manual health check
- [ ] "Enable/Disable" toggle works
- [ ] "Delete" button removes proxy
- [ ] Priority ordering works (drag-and-drop or up/down buttons)
- [ ] Real-time WebSocket updates reflected in UI

**Advanced Settings:**
- [ ] "Enable Proxy System" toggle works
- [ ] Health check interval configurable (minutes)
- [ ] Max consecutive failures configurable (1-10)
- [ ] Fallback to direct connection toggle works

### Integration

**Recording Flow:**
- [ ] Recording starts with healthy proxy
- [ ] Recording falls back to direct connection if all proxies fail
- [ ] Recording fails gracefully if fallback disabled
- [ ] WebSocket broadcasts proxy status changes
- [ ] Frontend shows real-time proxy health

---

## 🧪 Testing Checklist

### Unit Tests

**ProxyHealthService:**
```python
# tests/test_proxy_health_service.py
import pytest
from app.services.proxy.proxy_health_service import ProxyHealthService

@pytest.mark.asyncio
async def test_check_proxy_health_healthy():
    service = ProxyHealthService()
    result = await service.check_proxy_health("http://working-proxy:9999")
    assert result["status"] == "healthy"
    assert result["response_time_ms"] > 0

@pytest.mark.asyncio
async def test_check_proxy_health_failed():
    service = ProxyHealthService()
    result = await service.check_proxy_health("http://invalid:9999")
    assert result["status"] == "failed"
    assert "error" in result

@pytest.mark.asyncio
async def test_get_best_proxy():
    service = ProxyHealthService()
    best = await service.get_best_proxy()
    # Should return None if no proxies configured
    # Or best proxy URL if proxies exist
    assert best is None or isinstance(best, str)
```

### Integration Tests

**1. Add Multiple Proxies:**
```bash
# Add 3 proxies (1 working, 2 broken)
curl -X POST "http://localhost:8000/api/proxy/add" \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_url": "http://user:pass@working-proxy:9999",
    "priority": 0
  }'

curl -X POST "http://localhost:8000/api/proxy/add" \
  -d '{
    "proxy_url": "http://user:pass@broken-proxy1:9999",
    "priority": 1
  }'

curl -X POST "http://localhost:8000/api/proxy/add" \
  -d '{
    "proxy_url": "http://user:pass@broken-proxy2:9999",
    "priority": 2
  }'

# Verify proxies added
curl "http://localhost:8000/api/proxy/list"
# Expected: 3 proxies with priority 0, 1, 2
```

---

**2. Verify Health Checks:**
```bash
# Wait 5 minutes for automatic health check
sleep 300

# Check health status
curl "http://localhost:8000/api/proxy/list" | jq '.proxies[] | {proxy_url, health_status, response_time_ms}'

# Expected output:
# proxy_url: "http://user:***@working-proxy:9999"
# health_status: "healthy"
# response_time_ms: 123

# proxy_url: "http://user:***@broken-proxy1:9999"
# health_status: "failed"
# response_time_ms: 0

# proxy_url: "http://user:***@broken-proxy2:9999"
# health_status: "failed"
# response_time_ms: 0
```

---

**3. Test Proxy Selection:**
```python
# Start Python REPL
from app.services.proxy.proxy_health_service import get_proxy_health_service

service = get_proxy_health_service()
best = await service.get_best_proxy()

print(f"Best proxy: {best}")
# Expected: "http://user:pass@working-proxy:9999"
```

---

**4. Test Auto-Disable:**
```bash
# Manually mark proxy as failed 3 times
psql $DATABASE_URL -c "
  UPDATE proxy_settings 
  SET consecutive_failures = 3, health_status = 'failed' 
  WHERE id = 1;
"

# Trigger health check (wait 5 min or call manually)
curl -X POST "http://localhost:8000/api/proxy/1/test"

# Verify proxy auto-disabled
psql $DATABASE_URL -c "SELECT enabled FROM proxy_settings WHERE id = 1;"
# Expected: enabled = FALSE
```

---

**5. Test Recording with Proxy:**
```bash
# Add streamer
curl -X POST "http://localhost:8000/api/streamers" \
  -d '{"username": "xqc", "record": true}'

# Simulate stream.online event (mock or real)
# Check logs for proxy selection
docker logs streamvault-app | grep "Using proxy"

# Expected output:
# 2025-11-13 12:00:00 - streamvault - INFO - 🔗 Using proxy: http://user:***@working-proxy:9999...
```

---

**6. Test Fallback to Direct Connection:**
```bash
# Disable all proxies
curl -X POST "http://localhost:8000/api/proxy/1/toggle"  # Disable proxy 1
curl -X POST "http://localhost:8000/api/proxy/2/toggle"  # Disable proxy 2
curl -X POST "http://localhost:8000/api/proxy/3/toggle"  # Disable proxy 3

# Start recording
# Check logs for fallback message
docker logs streamvault-app | grep "direct connection"

# Expected output:
# 2025-11-13 12:00:00 - streamvault - WARNING - ⚠️ No healthy proxies available - using direct connection
```

---

**7. Test WebSocket Updates:**
```javascript
// Open browser console on http://localhost:8000
// WebSocket should receive proxy health updates

const ws = new WebSocket('ws://localhost:8000/ws')

ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  console.log('WebSocket message:', data)
}

// Wait 5 minutes for health check
// Expected messages:
// { type: "proxy_health_update", proxy: { id: 1, health_status: "healthy", ... } }
// { type: "proxy_health_update", proxy: { id: 2, health_status: "failed", ... } }
```

---

**8. Test Frontend UI:**
```
1. Open Settings → Proxy Settings
2. Verify system status shows: "1 of 3 proxies healthy"
3. Verify proxy list shows:
   - Proxy 1: ✅ HEALTHY (123ms)
   - Proxy 2: ❌ FAILED (Timeout)
   - Proxy 3: ❌ FAILED (Connection refused)
4. Click "Test" on Proxy 1 → Status refreshes
5. Click "Disable" on Proxy 1 → Badge changes to "DISABLED"
6. Click "Add Proxy" → Dialog opens
7. Enter proxy URL → Click "Add" → Proxy appears in list
8. Click "Delete" on Proxy 3 → Confirmation → Proxy removed
9. Toggle "Enable Proxy System" OFF → Status shows "DISABLED"
10. Toggle back ON → Status shows "1 of 2 proxies healthy"
```

---

## 📖 Documentation

**Primary Documentation:**
- `docs/BACKEND_FEATURES_PLANNED.md` (Section 2) - Complete implementation guide with code examples
- `docs/MASTER_TASK_LIST.md` (Task #3) - High-level overview and progress tracking

**Related Documentation:**
- `docs/COMPLETE_DESIGN_OVERHAUL_SUMMARY.md` - Frontend design patterns
- `docs/DESIGN_SYSTEM.md` - UI component reference
- `app/utils/streamlink_utils.py` - Current proxy implementation (to be replaced)

---

## 🤖 Copilot Instructions

### Context

**Current Problem:**
- Single proxy `http://serph91p:***@77.90.19.62:9999` is DOWN (500 error)
- ALL recordings fail after ~1 minute
- No fallback mechanism
- Manual intervention required to switch proxies

**Solution:**
Implement multi-proxy system with automatic health checks and failover at application level.

### Architecture Principles

**1. Application-Level Rotation:**
- Streamlink only supports 1 proxy per command
- Cannot do mid-recording proxy switching (limitation)
- Solution: Select best proxy BEFORE starting recording
- Future: Add mid-recording recovery (complex, deferred)

**2. Health Check Strategy:**
- Periodic checks (every 5 minutes) via background task
- Test connectivity with Twitch API endpoint (fast, reliable)
- Measure response time (milliseconds)
- Auto-disable after 3 consecutive failures
- WebSocket broadcasts updates to frontend

**3. Proxy Selection Algorithm:**
```
1. Filter: Only enabled proxies
2. Prioritize: healthy > degraded > failed
3. Sort: By priority (0 = highest)
4. Sort: By average_response_time_ms (faster = better)
5. Return: First match or None
```

**4. Fallback Strategy:**
- If all proxies fail AND `fallback_to_direct_connection=True`:
  - Use direct connection (no proxy)
  - Log warning
- If all proxies fail AND `fallback_to_direct_connection=False`:
  - Raise ProcessError
  - Recording fails

### Critical Patterns

**1. Database Transactions:**
```python
# Always use context manager for database sessions
with SessionLocal() as db:
    proxy = db.query(ProxySettings).first()
    proxy.health_status = "healthy"
    db.commit()  # CRITICAL: Always commit changes
```

**2. Async/Await:**
```python
# Health checks are async (don't block main thread)
async def check_proxy_health(self, proxy_url: str):
    async with httpx.AsyncClient(...) as client:
        response = await client.get(...)
    return {"status": "healthy", "response_time_ms": 123}
```

**3. Error Handling:**
```python
# Catch specific exceptions, don't let health check crash app
try:
    result = await self.check_proxy_health(proxy_url)
except asyncio.TimeoutError:
    return {"status": "failed", "error": "Timeout"}
except httpx.ProxyError as e:
    return {"status": "failed", "error": str(e)}
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return {"status": "failed", "error": str(e)}
```

**4. Logging:**
```python
# Use structured logging with context
logger.info(f"✅ Proxy health check passed: {proxy_url[:50]}... ({response_time_ms}ms)")
logger.warning(f"⚠️ No healthy proxies - using degraded proxy: {proxy_url[:50]}...")
logger.error(f"🚨 Proxy auto-disabled after 3 consecutive failures: {proxy_url[:50]}...")
```

**5. WebSocket Broadcasting:**
```python
# Broadcast proxy status updates to frontend
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

### Dependencies

**Python Packages:**
- `httpx` - Async HTTP client for health checks (already installed)
- `asyncio` - Async tasks for periodic health checks (stdlib)

**Database:**
- PostgreSQL (existing)
- New table: `proxy_settings`
- New columns in `recording_settings`

**External Services:**
- Twitch API (for health checks via https://api.twitch.tv/helix/streams)

### Testing Strategy

**Unit Tests:**
- `test_proxy_health_service.py` - Test health check logic
- Mock `httpx.AsyncClient` for deterministic tests
- Test timeout handling, error handling, status determination

**Integration Tests:**
- Add 3 proxies (1 working, 2 broken)
- Verify health checks run automatically
- Verify best proxy selected
- Verify auto-disable after 3 failures
- Verify fallback to direct connection
- Verify WebSocket broadcasts

**Manual Testing:**
- Test via browser UI (Settings → Proxy Settings)
- Add/Remove/Test/Toggle proxies
- Verify real-time health updates
- Start recording → Verify proxy used in logs

### Files to Read First

**Before Coding:**
1. `docs/BACKEND_FEATURES_PLANNED.md` (Section 2) - Complete architecture
2. `app/services/recording/process_manager.py` - Current proxy usage (line 171-212)
3. `app/utils/streamlink_utils.py` - Proxy connectivity check (line 54-110)
4. `app/models.py` - Current GlobalSettings model (line 215-237)

**For Frontend:**
5. `docs/DESIGN_SYSTEM.md` - UI component patterns
6. `app/frontend/src/views/SettingsView.vue` - Settings panel structure

### Success Criteria

**Definition of Done:**
- [ ] Migration 025 runs successfully
- [ ] ProxySettings model created
- [ ] ProxyHealthService implemented
- [ ] Health checks run every 5 minutes
- [ ] Proxies auto-disable after 3 failures
- [ ] ProcessManager uses best available proxy
- [ ] Fallback to direct connection works
- [ ] API endpoints functional (list/add/remove/test/toggle)
- [ ] Frontend UI displays proxy list with health badges
- [ ] WebSocket updates work in real-time
- [ ] Recording starts with healthy proxy
- [ ] All tests pass

**Known Limitations:**
- Cannot switch proxy mid-recording (Streamlink limitation)
- Health checks run every 5 minutes (not real-time)
- WebSocket updates depend on frontend connection
- Proxy credentials visible in database (consider encryption in future)

### Common Pitfalls

**❌ Don't:**
- Hardcode proxy URLs in code
- Block main thread with synchronous health checks
- Forget to commit database changes
- Let health check failures crash the app
- Expose full proxy URLs (with passwords) in API responses without masking

**✅ Do:**
- Use async/await for I/O operations
- Catch specific exceptions (TimeoutError, ProxyError, etc.)
- Log all proxy selection decisions
- Mask passwords in logs and API responses
- Test with real proxies (working and broken)

### Future Enhancements

**Not in Scope (Deferred):**
1. Mid-recording proxy switching (complex, needs Streamlink process restart)
2. Proxy credential encryption (security improvement)
3. Proxy geographic location tracking
4. Proxy bandwidth usage tracking
5. Proxy cost tracking (for paid proxies)
6. Proxy rotation based on streamer (different proxies for different streamers)

**For Later Sprints:**
- Issue #15: Mid-recording proxy recovery
- Issue #16: Proxy credential encryption
- Issue #17: Advanced proxy analytics

---

## 📊 Summary - Implementation Checklist

### Phase 1: Database (30 min)
- [ ] Create `migrations/025_add_multi_proxy_support.py`
- [ ] Run migration → `proxy_settings` table created
- [ ] Migrate existing proxy from `global_settings`
- [ ] Verify indexes created

### Phase 2: Backend Service (60-90 min)
- [ ] Create `app/services/proxy/__init__.py`
- [ ] Create `app/services/proxy/proxy_health_service.py`
- [ ] Implement `check_proxy_health()`
- [ ] Implement `get_best_proxy()`
- [ ] Implement `run_health_checks()` background task
- [ ] Add singleton pattern

### Phase 3: Process Manager (30 min)
- [ ] Update `app/services/recording/process_manager.py`
- [ ] Replace `get_proxy_settings_from_db()` with `get_best_proxy()`
- [ ] Add fallback logic
- [ ] Update logging

### Phase 4: API Endpoints (30-45 min)
- [ ] Create `app/routes/proxy.py`
- [ ] Implement GET `/api/proxy/list`
- [ ] Implement POST `/api/proxy/add`
- [ ] Implement DELETE `/api/proxy/{id}`
- [ ] Implement POST `/api/proxy/{id}/toggle`
- [ ] Implement POST `/api/proxy/{id}/test`
- [ ] Implement POST `/api/proxy/{id}/update-priority`

### Phase 5: Models (15 min)
- [ ] Update `app/models.py`
- [ ] Add `ProxySettings` model
- [ ] Update `RecordingSettings` model

### Phase 6: Main App (15 min)
- [ ] Update `app/main.py`
- [ ] Register proxy routes
- [ ] Add startup event → `proxy_service.start()`
- [ ] Add shutdown event → `proxy_service.stop()`

### Phase 7: Frontend (60-90 min)
- [ ] Create `app/frontend/src/types/proxy.ts`
- [ ] Create `app/frontend/src/composables/useProxySettings.ts`
- [ ] Create `app/frontend/src/components/settings/ProxySettingsPanel.vue`
- [ ] Update `app/frontend/src/views/SettingsView.vue`

### Phase 8: Testing (30-45 min)
- [ ] Unit tests for ProxyHealthService
- [ ] Integration test: Add 3 proxies
- [ ] Integration test: Verify health checks
- [ ] Integration test: Test proxy selection
- [ ] Integration test: Test auto-disable
- [ ] Integration test: Test recording with proxy
- [ ] Integration test: Test fallback
- [ ] Integration test: Test WebSocket updates
- [ ] Manual test: Frontend UI

**Total Estimated Time:** 3-4 hours (Backend: 2-3h, Frontend: 1h, Testing: 30-45min)

---

**End of Issue #2 Documentation**

*This issue is CRITICAL and blocks production recordings. Implement as Sprint 1 Hotfix priority.*
