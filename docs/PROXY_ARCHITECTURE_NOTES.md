# Multi-Proxy System Architecture Notes

## Issue Resolution (Nov 13, 2025)

### Problem
The ProxySettingsPanel was failing with:
```
TypeError: can't access property "enable_proxy", H.value is undefined
```

### Root Cause
The `/api/proxy/list` endpoint was not returning the `system_config` object that the frontend composable expected.

### Fix Applied
1. **Backend API (`app/routes/proxy.py`)**:
   - Added `ProxyConfigSettings` Pydantic model
   - Modified `/api/proxy/list` to query `RecordingSettings` and return proxy config
   - Config includes: enable_proxy, proxy_health_check_enabled, intervals, thresholds, fallback settings

2. **Model Serialization (`app/models.py`)**:
   - Updated `ProxySettings.to_dict()` to match frontend TypeScript interface exactly
   - Renamed fields: `last_health_check` → `last_check`, `average_response_time_ms` → `response_time_ms`
   - Added `masked_url` field for consistent display
   - Added calculated fields: `successful_requests` = total - failed

### Architecture: Two Proxy Systems

**Old System (RecordingSettingsPanel → Network tab)**:
- Simple HTTP/HTTPS proxy configuration
- Stored in `GlobalSettings` table (http_proxy, https_proxy columns)
- Direct passthrough to Streamlink `--http-proxy` argument
- No health checking or failover

**New System (ProxySettingsPanel - separate tab)**:
- Multi-proxy management with priority-based selection
- Stored in dedicated `proxy_settings` table
- Automatic health monitoring (every 5 minutes)
- Intelligent failover (best available proxy)
- Configurable via `RecordingSettings` columns:
  - enable_proxy
  - proxy_health_check_enabled
  - proxy_health_check_interval_seconds
  - proxy_max_consecutive_failures
  - fallback_to_direct_connection

### Recommendation
- **Keep both systems** for now (migration path exists)
- Users can:
  1. Start simple: Use Network tab for single proxy
  2. Upgrade later: Add multiple proxies in Proxy Management tab
- Future: Consider migrating old proxy URLs to new system automatically

### Migration Path
1. User sets HTTP proxy in Network tab → Saves to GlobalSettings
2. On first Proxy Management visit, offer to migrate:
   - "Detected proxy in old settings. Import to multi-proxy system?"
   - Creates ProxySettings entry with priority 0
   - Enables health checks by default
3. User can then add additional proxies for redundancy

### API Endpoints
- `GET /api/proxy/list` - List all proxies + system config
- `POST /api/proxy/add` - Add new proxy
- `DELETE /api/proxy/{id}` - Remove proxy
- `POST /api/proxy/{id}/toggle` - Enable/disable proxy
- `POST /api/proxy/{id}/test` - Manual health check
- `POST /api/proxy/{id}/update-priority` - Change priority
- `GET /api/proxy/best` - Get currently selected best proxy
- `POST /api/proxy/config/update` - Update system config

### Frontend Components
- **ProxySettingsPanel.vue** - Main UI for multi-proxy management
- **useProxySettings.ts** - Composable for state/API calls
- **types/proxy.ts** - TypeScript interfaces

### Database Schema
```sql
-- Multi-proxy table
CREATE TABLE proxy_settings (
  id SERIAL PRIMARY KEY,
  proxy_url VARCHAR NOT NULL,  -- Encrypted with Fernet
  priority INTEGER NOT NULL DEFAULT 0,
  enabled BOOLEAN NOT NULL DEFAULT true,
  health_status VARCHAR NOT NULL DEFAULT 'unknown',
  last_health_check TIMESTAMP WITH TIME ZONE,
  consecutive_failures INTEGER NOT NULL DEFAULT 0,
  average_response_time_ms INTEGER,
  total_recordings INTEGER NOT NULL DEFAULT 0,
  failed_recordings INTEGER NOT NULL DEFAULT 0,
  -- ... other fields
);

-- System config in recording_settings
ALTER TABLE recording_settings ADD COLUMN enable_proxy BOOLEAN DEFAULT true;
ALTER TABLE recording_settings ADD COLUMN proxy_health_check_enabled BOOLEAN DEFAULT true;
ALTER TABLE recording_settings ADD COLUMN proxy_health_check_interval_seconds INTEGER DEFAULT 300;
ALTER TABLE recording_settings ADD COLUMN proxy_max_consecutive_failures INTEGER DEFAULT 3;
ALTER TABLE recording_settings ADD COLUMN fallback_to_direct_connection BOOLEAN DEFAULT true;
```

### Testing Checklist
- [ ] Backend starts without errors
- [ ] `/api/proxy/list` returns proxies + system_config
- [ ] ProxySettingsPanel loads without TypeError
- [ ] Can add/remove proxies via UI
- [ ] Health checks run automatically
- [ ] WebSocket updates work in real-time
- [ ] Recording uses selected best proxy
