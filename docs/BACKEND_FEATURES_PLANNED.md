# Backend Features - Implementation Plan

## 🎯 **HIGH PRIORITY FEATURES**

### 1. H.265/AV1 Codec Support (Streamlink 8.0.0+)

**Status**: ✅ **IMPLEMENTED** - Needs Testing  
**Priority**: HIGH  
**Breaking Changes**: None (backward compatible)  
**Streamlink Version Required**: 8.0.0+  
**Implementation Commits**: b219ad1e, c415ec28, da591a46, 7aba76ce, 820032de

#### Background

Twitch now allows streamers to broadcast in higher quality using modern codecs:
- **H.265 (HEVC)**: Up to 1440p60 on some channels
- **AV1**: Up to 1440p60 (experimental, rare)
- **H.264 (legacy)**: Maximum 1080p60 (current default)

With Streamlink 8.0.0, the new `--twitch-supported-codecs` argument allows requesting higher quality streams.

#### Technical Details

**Streamlink Argument**:
```bash
--twitch-supported-codecs=h264,h265,av1
```

**Available Codec Combinations**:
- `h264` (default) - Maximum 1080p60, widest compatibility
- `h265` - Access to 1440p60 streams (if broadcaster supports it)
- `av1` - Access to AV1 streams (very rare, experimental)
- `h264,h265` - Prefer h265, fallback to h264 (RECOMMENDED)
- `h264,h265,av1` - All codecs enabled (future-proof)

**Stream Availability Example** (from Streamlink docs):
```
h264 only:
- 480p30 (h264)
- audio_only

h265 enabled:
- 1440p60 (AV1) - chunked quality
- 720p60 (H.265/HEVC)
- 480p30 (h264) - fallback
- audio_only

av1,h264:
- 1440p60 (AV1)
- 480p30 (h264)
- audio_only
```

**Important Notes**:
1. Higher quality streams depend on **broadcaster settings**
2. Not all channels stream in h265/av1 (most still use h264)
3. Re-encoded lower qualities might still be h264 even with h265 enabled
4. AV1 decode requires modern hardware (2020+)

#### Implementation Plan

**Database Changes** (Migration required):
```python
# Migration: 024_add_codec_preferences.py
class RecordingSettings(Base):
    # NEW FIELDS
    supported_codecs = Column(String, default="h264,h265")  # Default: h264 with h265 fallback
    prefer_higher_quality = Column(Boolean, default=True)   # Auto-select highest available quality
```

**Backend Changes**:

1. **app/config/constants.py**:
```python
# Streamlink Codec Constants
SUPPORTED_CODECS = {
    "h264": "H.264 (1080p max, highest compatibility)",
    "h265": "H.265/HEVC (1440p capable, modern hardware)",
    "av1": "AV1 (experimental, rare, newest hardware)",
    "h264,h265": "H.264 + H.265 (RECOMMENDED - best quality/compatibility balance)",
    "h264,h265,av1": "All Codecs (future-proof, requires AV1 decode support)"
}

DEFAULT_CODEC_PREFERENCE = "h264,h265"  # Safe default
```

2. **app/services/recording/process_manager.py**:
```python
def _build_streamlink_command(self, ...):
    # Add codec preference to streamlink command
    codec_preference = recording_settings.supported_codecs or "h264,h265"
    
    command.extend([
        "--twitch-supported-codecs", codec_preference
    ])
```

3. **app/routes/recording.py**:
```python
# GET /api/recording/codec-options
async def get_codec_options():
    """Get available codec options with descriptions"""
    return {
        "codecs": SUPPORTED_CODECS,
        "default": DEFAULT_CODEC_PREFERENCE,
        "recommended": "h264,h265"
    }

# POST /api/recording/settings
async def update_recording_settings(
    supported_codecs: str = "h264,h265"
):
    # Validate codec string
    valid_codecs = ["h264", "h265", "av1"]
    requested = [c.strip() for c in supported_codecs.split(",")]
    
    if not all(c in valid_codecs for c in requested):
        raise HTTPException(400, "Invalid codec specified")
    
    settings.supported_codecs = supported_codecs
```

**Frontend Changes**:

1. **app/frontend/src/types/settings.ts** (Update Interface):
```typescript
export interface RecordingSettings {
  // ... existing fields
  
  // NEW: Codec support
  supported_codecs: string  // "h264,h265" | "h264" | "h264,h265,av1" etc.
  prefer_higher_quality: boolean
}

export interface CodecOption {
  value: string
  label: string
  description: string
  maxResolution: string
  compatibility: 'high' | 'medium' | 'low'
  requiresModernHardware: boolean
}
```

2. **app/frontend/src/composables/useRecordingSettings.ts** (Add Codec Methods):
```typescript
import { ref, computed } from 'vue'
import type { RecordingSettings, CodecOption } from '@/types/settings'

export function useRecordingSettings() {
  const settings = ref<RecordingSettings>({
    // ... existing fields
    supported_codecs: 'h264,h265',  // Default
    prefer_higher_quality: true
  })
  
  // NEW: Fetch available codec options from backend
  const codecOptions = ref<CodecOption[]>([])
  
  async function fetchCodecOptions() {
    const response = await fetch('/api/recording/codec-options', {
      credentials: 'include'
    })
    const data = await response.json()
    
    // Transform backend response to frontend format
    codecOptions.value = [
      {
        value: 'h264',
        label: 'H.264 Only',
        description: 'Maximum compatibility, up to 1080p60',
        maxResolution: '1080p60',
        compatibility: 'high',
        requiresModernHardware: false
      },
      {
        value: 'h264,h265',
        label: 'H.264 + H.265 (Recommended)',
        description: 'Best balance - 1440p60 capable with fallback',
        maxResolution: '1440p60',
        compatibility: 'high',
        requiresModernHardware: false
      },
      {
        value: 'h264,h265,av1',
        label: 'All Codecs (Future-proof)',
        description: 'All formats supported, requires modern hardware',
        maxResolution: '1440p60+',
        compatibility: 'medium',
        requiresModernHardware: true
      },
      {
        value: 'h265',
        label: 'H.265 Only (Experimental)',
        description: 'High efficiency, may have compatibility issues',
        maxResolution: '1440p60',
        compatibility: 'medium',
        requiresModernHardware: false
      },
      {
        value: 'av1',
        label: 'AV1 Only (Very Experimental)',
        description: 'Cutting edge, requires very modern hardware',
        maxResolution: '1440p60',
        compatibility: 'low',
        requiresModernHardware: true
      }
    ]
  }
  
  // NEW: Validate codec selection
  const selectedCodecOption = computed(() => {
    return codecOptions.value.find(opt => opt.value === settings.value.supported_codecs)
  })
  
  const codecWarnings = computed(() => {
    const warnings: string[] = []
    const selected = selectedCodecOption.value
    
    if (!selected) return warnings
    
    if (selected.requiresModernHardware) {
      warnings.push('⚠️ This codec requires modern hardware (2020+) for smooth playback')
    }
    
    if (selected.compatibility === 'low') {
      warnings.push('⚠️ Low compatibility - older devices may not be able to play recordings')
    }
    
    if (!selected.value.includes('h264')) {
      warnings.push('⚠️ No H.264 fallback - some streams may not be recordable')
    }
    
    return warnings
  })
  
  async function updateCodecSettings(newCodec: string) {
    settings.value.supported_codecs = newCodec
    
    const response = await fetch('/api/recording/settings', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        supported_codecs: newCodec,
        prefer_higher_quality: settings.value.prefer_higher_quality
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to update codec settings')
    }
  }
  
  return {
    settings,
    codecOptions,
    selectedCodecOption,
    codecWarnings,
    fetchCodecOptions,
    updateCodecSettings
  }
}
```

3. **app/frontend/src/views/SettingsView.vue** (Update Settings View):
```vue
<template>
  <div class="settings-view">
    <!-- ... existing sections ... -->
    
    <!-- NEW: Codec Settings Section -->
    <section class="settings-section">
      <h2>Video Codec Settings</h2>
      <CodecSettingsPanel />
    </section>
    
    <!-- NEW: Proxy Settings Section -->
    <section class="settings-section">
      <h2>Proxy Configuration</h2>
      <ProxySettingsPanel />
    </section>
  </div>
</template>

<script setup lang="ts">
import CodecSettingsPanel from '@/components/settings/CodecSettingsPanel.vue'
import ProxySettingsPanel from '@/components/settings/ProxySettingsPanel.vue'
</script>
```

4. **app/frontend/src/components/settings/CodecSettingsPanel.vue** (NEW Component):
```vue
<template>
  <div class="codec-settings-panel card">
    <div class="panel-header">
      <h3>Video Codec Preferences</h3>
      <p class="subtitle">
        Choose which video codecs Streamlink should request from Twitch.
        Higher quality streams (1440p) require H.265 or AV1 support.
      </p>
    </div>
    
    <div class="form-group">
      <label class="form-label">Codec Selection</label>
      
      <div class="codec-options">
        <div
          v-for="option in codecOptions"
          :key="option.value"
          class="codec-option"
          :class="{ 
            selected: settings.supported_codecs === option.value,
            recommended: option.value === 'h264,h265'
          }"
          @click="selectCodec(option.value)"
        >
          <div class="option-header">
            <input
              type="radio"
              :id="`codec-${option.value}`"
              :value="option.value"
              v-model="settings.supported_codecs"
              @change="handleCodecChange"
            />
            <label :for="`codec-${option.value}`" class="option-title">
              {{ option.label }}
              <span v-if="option.value === 'h264,h265'" class="badge badge-success">
                Recommended
              </span>
            </label>
          </div>
          
          <p class="option-description">{{ option.description }}</p>
          
          <div class="option-details">
            <span class="detail-item">
              📺 Max: {{ option.maxResolution }}
            </span>
            <span class="detail-item" :class="`compatibility-${option.compatibility}`">
              {{ compatibilityLabel(option.compatibility) }}
            </span>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Warnings Display -->
    <div v-if="codecWarnings.length > 0" class="warnings-section">
      <div
        v-for="(warning, index) in codecWarnings"
        :key="index"
        class="alert alert-warning"
      >
        {{ warning }}
      </div>
    </div>
    
    <!-- Info Box -->
    <div class="info-box">
      <h4>ℹ️ About Video Codecs</h4>
      <ul>
        <li><strong>H.264:</strong> Universal compatibility, maximum 1080p60</li>
        <li><strong>H.265 (HEVC):</strong> Up to 1440p60, ~30% smaller files, modern devices</li>
        <li><strong>AV1:</strong> Cutting edge, rare on Twitch, requires newest hardware</li>
      </ul>
      <p class="note">
        <strong>Note:</strong> Actual available quality depends on the broadcaster's settings.
        Most channels still stream in H.264 (1080p max).
      </p>
    </div>
    
    <!-- Higher Quality Toggle -->
    <div class="form-group">
      <label class="checkbox-label">
        <input
          type="checkbox"
          v-model="settings.prefer_higher_quality"
          @change="handleCodecChange"
        />
        <span>Automatically select highest available quality</span>
      </label>
      <p class="help-text">
        When enabled, Streamlink will choose the best quality stream available.
        Disable to manually select quality per recording.
      </p>
    </div>
    
    <!-- Save Button -->
    <div class="form-actions">
      <button
        @click="saveSettings"
        :disabled="isSaving"
        class="btn btn-primary"
      >
        {{ isSaving ? 'Saving...' : 'Save Codec Settings' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRecordingSettings } from '@/composables/useRecordingSettings'

const {
  settings,
  codecOptions,
  selectedCodecOption,
  codecWarnings,
  fetchCodecOptions,
  updateCodecSettings
} = useRecordingSettings()

const isSaving = ref(false)

onMounted(async () => {
  await fetchCodecOptions()
})

function compatibilityLabel(level: string): string {
  const labels = {
    high: '✅ High Compatibility',
    medium: '⚠️ Medium Compatibility',
    low: '❌ Low Compatibility'
  }
  return labels[level] || 'Unknown'
}

function selectCodec(value: string) {
  settings.value.supported_codecs = value
}

async function handleCodecChange() {
  // Auto-save on change (optional)
  // await saveSettings()
}

async function saveSettings() {
  isSaving.value = true
  
  try {
    await updateCodecSettings(settings.value.supported_codecs)
    
    // Show success toast
    console.log('✅ Codec settings saved successfully')
  } catch (error) {
    console.error('❌ Failed to save codec settings:', error)
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.codec-settings-panel {
  padding: v.$spacing-4;
}

.panel-header {
  margin-bottom: v.$spacing-4;
  
  h3 {
    margin-bottom: v.$spacing-2;
    font-size: 1.25rem;
  }
  
  .subtitle {
    color: var(--text-secondary);
    font-size: 0.875rem;
  }
}

.codec-options {
  display: grid;
  gap: v.$spacing-3;
}

.codec-option {
  padding: v.$spacing-3;
  border: 2px solid var(--border-color);
  border-radius: v.$border-radius-md;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    border-color: var(--primary-color);
    background: var(--bg-hover);
  }
  
  &.selected {
    border-color: var(--primary-color);
    background: rgba(var(--primary-color-rgb), 0.1);
  }
  
  &.recommended {
    position: relative;
    border-color: var(--success-color);
  }
}

.option-header {
  display: flex;
  align-items: center;
  gap: v.$spacing-2;
  margin-bottom: v.$spacing-2;
  
  .option-title {
    display: flex;
    align-items: center;
    gap: v.$spacing-2;
    font-weight: 600;
    cursor: pointer;
  }
}

.option-description {
  margin-left: 28px;
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: v.$spacing-2;
}

.option-details {
  display: flex;
  gap: v.$spacing-3;
  margin-left: 28px;
  font-size: 0.75rem;
  
  .detail-item {
    padding: 4px 8px;
    border-radius: v.$border-radius-sm;
    background: var(--bg-tertiary);
    
    &.compatibility-high {
      color: var(--success-color);
    }
    
    &.compatibility-medium {
      color: var(--warning-color);
    }
    
    &.compatibility-low {
      color: var(--danger-color);
    }
  }
}

.warnings-section {
  margin-top: v.$spacing-4;
  display: flex;
  flex-direction: column;
  gap: v.$spacing-2;
}

.info-box {
  margin-top: v.$spacing-4;
  padding: v.$spacing-3;
  background: var(--bg-secondary);
  border-radius: v.$border-radius-md;
  border-left: 4px solid var(--primary-color);
  
  h4 {
    margin-bottom: v.$spacing-2;
    font-size: 1rem;
  }
  
  ul {
    margin-left: v.$spacing-4;
    margin-bottom: v.$spacing-2;
    
    li {
      margin-bottom: v.$spacing-1;
      color: var(--text-secondary);
    }
  }
  
  .note {
    margin-top: v.$spacing-2;
    padding-top: v.$spacing-2;
    border-top: 1px solid var(--border-color);
    font-size: 0.875rem;
    color: var(--text-secondary);
  }
}

.form-actions {
  margin-top: v.$spacing-4;
  display: flex;
  justify-content: flex-end;
}
</style>
```

**Validation & Testing**:
- Test with h264-only channel (most channels)
- Test with h265-capable channel (1440p streamer)
- Verify fallback to h264 when h265 not available
- Check file sizes (h265 = ~30% smaller than h264 at same quality)
- Test playback compatibility on various devices

**Rollback Plan**:
If issues arise, default back to `h264` in constants.py - no data loss.

---

### 2. Multi-Proxy Support with Health Checks

**Status**: 📝 Documented - Ready for Implementation  
**Priority**: CRITICAL (current proxy is DOWN, recordings fail)  
**Breaking Changes**: None (backward compatible with single proxy)

#### Background

**Current Problem**:
- Single proxy: `http://serph91p:***@77.90.19.62:9999`
- Status: **500 Internal Server Error**
- Result: ALL recordings fail after ~1 minute
- No fallback mechanism

**Streamlink Behavior**:
```bash
--http-proxy http://proxy1.example.com:9999
```
- Only supports ONE proxy at a time
- No built-in failover
- If proxy fails → recording fails

#### Implementation Plan

**Solution**: Application-level proxy rotation with health checks

**Database Changes**:
```python
# Migration: 025_add_multi_proxy_support.py
class ProxySettings(Base):
    __tablename__ = "proxy_settings"
    
    id = Column(Integer, primary_key=True)
    proxy_url = Column(String, nullable=False)  # http://user:pass@host:port
    priority = Column(Integer, default=0)        # 0 = highest priority
    enabled = Column(Boolean, default=True)
    
    # Health check data
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String)  # "healthy", "degraded", "failed"
    consecutive_failures = Column(Integer, default=0)
    average_response_time_ms = Column(Integer)
    
    # Statistics
    total_recordings = Column(Integer, default=0)
    failed_recordings = Column(Integer, default=0)
    success_rate = Column(Float)  # Calculated: (total - failed) / total

# Update RecordingSettings
class RecordingSettings(Base):
    # NEW FIELDS
    enable_proxy = Column(Boolean, default=True)
    proxy_health_check_enabled = Column(Boolean, default=True)
    proxy_health_check_interval_seconds = Column(Integer, default=300)  # 5 minutes
    proxy_max_consecutive_failures = Column(Integer, default=3)
    fallback_to_direct_connection = Column(Boolean, default=True)
```

**Backend Changes**:

1. **app/services/proxy/proxy_health_service.py** (NEW):
```python
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
            response = await asyncio.wait_for(
                self._test_request(proxy_url, "https://api.twitch.tv/helix/streams"),
                timeout=10.0  # 10 second timeout
            )
            
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

2. **app/services/recording/process_manager.py**:
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

3. **app/routes/proxy.py** (NEW):
```python
@router.get("/api/proxy/list")
async def get_proxies():
    """Get all configured proxies with health status"""
    with SessionLocal() as db:
        proxies = db.query(ProxySettings).all()
        return {
            "proxies": [
                {
                    "id": p.id,
                    "proxy_url": p.proxy_url,  # Mask password in response
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
async def add_proxy(
    proxy_url: str,
    priority: int = 0
):
    """Add new proxy"""
    # Validate proxy URL format
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
        from app.services.proxy.proxy_health_service import ProxyHealthService
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
        
        from app.services.proxy.proxy_health_service import ProxyHealthService
        health_service = ProxyHealthService()
        
        result = await health_service.check_proxy_health(proxy.proxy_url)
        
        # Update database
        proxy.last_health_check = datetime.now(timezone.utc)
        proxy.health_status = result["status"]
        proxy.average_response_time_ms = result.get("response_time_ms", 0)
        db.commit()
        
        return result
```

**Frontend Changes**:

1. **app/frontend/src/types/proxy.ts** (NEW Type Definitions):
```typescript
export interface ProxySettings {
  id: number
  proxy_url: string
  priority: number
  enabled: boolean
  health_status: 'healthy' | 'degraded' | 'failed' | 'unknown'
  last_health_check: string | null
  average_response_time_ms: number | null
  consecutive_failures: number
  success_rate: number | null
  total_recordings: number
  failed_recordings: number
}

export interface ProxyHealthCheckResult {
  status: 'healthy' | 'degraded' | 'failed'
  response_time_ms: number
  error?: string
}

export interface ProxyConfigSettings {
  enable_proxy: boolean
  proxy_health_check_enabled: boolean
  proxy_health_check_interval_seconds: number
  proxy_max_consecutive_failures: number
  fallback_to_direct_connection: boolean
}
```

2. **app/frontend/src/composables/useProxySettings.ts** (NEW Composable):
```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { ProxySettings, ProxyConfigSettings, ProxyHealthCheckResult } from '@/types/proxy'
import { useWebSocket } from './useWebSocket'

export function useProxySettings() {
  const proxies = ref<ProxySettings[]>([])
  const config = ref<ProxyConfigSettings>({
    enable_proxy: true,
    proxy_health_check_enabled: true,
    proxy_health_check_interval_seconds: 300,
    proxy_max_consecutive_failures: 3,
    fallback_to_direct_connection: true
  })
  
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  
  // WebSocket for real-time health updates
  const { subscribe, unsubscribe } = useWebSocket()
  
  // Computed: Sort proxies by priority and health
  const sortedProxies = computed(() => {
    return [...proxies.value].sort((a, b) => {
      // Priority first
      if (a.priority !== b.priority) {
        return a.priority - b.priority
      }
      // Then health status
      const healthOrder = { healthy: 0, degraded: 1, failed: 2, unknown: 3 }
      return healthOrder[a.health_status] - healthOrder[b.health_status]
    })
  })
  
  // Computed: Healthy proxy count
  const healthyProxyCount = computed(() => {
    return proxies.value.filter(p => p.health_status === 'healthy' && p.enabled).length
  })
  
  // Computed: System status
  const proxySystemStatus = computed(() => {
    if (!config.value.enable_proxy) {
      return { status: 'disabled', message: 'Proxy system disabled - using direct connection' }
    }
    
    const enabledProxies = proxies.value.filter(p => p.enabled)
    if (enabledProxies.length === 0) {
      return { status: 'warning', message: 'No proxies configured' }
    }
    
    const healthy = enabledProxies.filter(p => p.health_status === 'healthy')
    if (healthy.length === 0) {
      if (config.value.fallback_to_direct_connection) {
        return { status: 'degraded', message: 'All proxies down - using direct connection fallback' }
      } else {
        return { status: 'error', message: 'All proxies down - recordings will fail' }
      }
    }
    
    return { 
      status: 'healthy', 
      message: `${healthy.length} of ${enabledProxies.length} proxies healthy` 
    }
  })
  
  // Fetch all proxies
  async function fetchProxies() {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch('/api/proxy/list', {
        credentials: 'include'
      })
      
      if (!response.ok) {
        throw new Error(`Failed to fetch proxies: ${response.statusText}`)
      }
      
      const data = await response.json()
      proxies.value = data.proxies
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to fetch proxies:', err)
    } finally {
      isLoading.value = false
    }
  }
  
  // Fetch proxy configuration
  async function fetchConfig() {
    try {
      const response = await fetch('/api/proxy/config', {
        credentials: 'include'
      })
      
      if (response.ok) {
        const data = await response.json()
        config.value = data
      }
    } catch (err) {
      console.error('Failed to fetch proxy config:', err)
    }
  }
  
  // Add new proxy
  async function addProxy(proxyUrl: string, priority: number = 0) {
    try {
      const response = await fetch('/api/proxy/add', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proxy_url: proxyUrl, priority })
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to add proxy')
      }
      
      await fetchProxies()  // Refresh list
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add proxy'
      return { success: false, error: message }
    }
  }
  
  // Remove proxy
  async function removeProxy(proxyId: number) {
    try {
      const response = await fetch(`/api/proxy/${proxyId}`, {
        method: 'DELETE',
        credentials: 'include'
      })
      
      if (!response.ok) {
        throw new Error('Failed to remove proxy')
      }
      
      await fetchProxies()  // Refresh list
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to remove proxy'
      return { success: false, error: message }
    }
  }
  
  // Test proxy connectivity
  async function testProxy(proxyId: number): Promise<ProxyHealthCheckResult> {
    try {
      const response = await fetch(`/api/proxy/${proxyId}/test`, {
        method: 'POST',
        credentials: 'include'
      })
      
      if (!response.ok) {
        throw new Error('Health check request failed')
      }
      
      const result: ProxyHealthCheckResult = await response.json()
      
      // Update local state
      await fetchProxies()
      
      return result
    } catch (err) {
      return {
        status: 'failed',
        response_time_ms: 0,
        error: err instanceof Error ? err.message : 'Unknown error'
      }
    }
  }
  
  // Toggle proxy enabled/disabled
  async function toggleProxy(proxyId: number) {
    try {
      const response = await fetch(`/api/proxy/${proxyId}/toggle`, {
        method: 'POST',
        credentials: 'include'
      })
      
      if (!response.ok) {
        throw new Error('Failed to toggle proxy')
      }
      
      await fetchProxies()
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to toggle proxy'
      return { success: false, error: message }
    }
  }
  
  // Update proxy priority
  async function updateProxyPriority(proxyId: number, newPriority: number) {
    try {
      const response = await fetch(`/api/proxy/${proxyId}/priority`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority: newPriority })
      })
      
      if (!response.ok) {
        throw new Error('Failed to update priority')
      }
      
      await fetchProxies()
      return { success: true }
    } catch (err) {
      return { success: false, error: err.message }
    }
  }
  
  // Update proxy configuration
  async function updateConfig(newConfig: Partial<ProxyConfigSettings>) {
    try {
      const response = await fetch('/api/proxy/config', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      })
      
      if (!response.ok) {
        throw new Error('Failed to update proxy config')
      }
      
      await fetchConfig()
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update config'
      return { success: false, error: message }
    }
  }
  
  // WebSocket: Listen for proxy health updates
  function setupWebSocketListener() {
    subscribe('proxy_health_update', (data: any) => {
      // Update proxy in local state
      const index = proxies.value.findIndex(p => p.id === data.proxy_id)
      if (index !== -1) {
        proxies.value[index] = {
          ...proxies.value[index],
          health_status: data.health_status,
          last_health_check: data.last_health_check,
          average_response_time_ms: data.average_response_time_ms,
          consecutive_failures: data.consecutive_failures
        }
      }
    })
  }
  
  // Lifecycle
  onMounted(() => {
    fetchProxies()
    fetchConfig()
    setupWebSocketListener()
  })
  
  onUnmounted(() => {
    unsubscribe('proxy_health_update')
  })
  
  return {
    proxies,
    sortedProxies,
    config,
    healthyProxyCount,
    proxySystemStatus,
    isLoading,
    error,
    fetchProxies,
    addProxy,
    removeProxy,
    testProxy,
    toggleProxy,
    updateProxyPriority,
    updateConfig
  }
}
```

3. **app/frontend/src/components/settings/ProxySettingsPanel.vue** (NEW Component):
```vue
<template>
  <div class="proxy-settings-panel card">
    <!-- System Status Header -->
    <div class="system-status" :class="`status-${proxySystemStatus.status}`">
      <div class="status-icon">
        <span v-if="proxySystemStatus.status === 'healthy'">✅</span>
        <span v-else-if="proxySystemStatus.status === 'degraded'">⚠️</span>
        <span v-else-if="proxySystemStatus.status === 'error'">❌</span>
        <span v-else>ℹ️</span>
      </div>
      <div class="status-message">
        <h4>Proxy System Status</h4>
        <p>{{ proxySystemStatus.message }}</p>
      </div>
    </div>
    
    <!-- Enable Proxy Toggle -->
    <div class="config-section">
      <div class="form-group">
        <label class="checkbox-label">
          <input
            type="checkbox"
            v-model="config.enable_proxy"
            @change="updateProxyConfig"
          />
          <span>Enable HTTP Proxy for Recordings</span>
        </label>
        <p class="help-text">
          Use HTTP proxies to route Streamlink traffic. Disable to use direct connection.
        </p>
      </div>
    </div>
    
    <!-- Proxy List -->
    <div v-if="config.enable_proxy" class="proxy-list-section">
      <div class="section-header">
        <h3>Configured Proxies</h3>
        <button @click="showAddProxy = true" class="btn btn-primary btn-sm">
          + Add Proxy
        </button>
      </div>
      
      <!-- Loading State -->
      <div v-if="isLoading" class="loading-state">
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-card"></div>
      </div>
      
      <!-- Empty State -->
      <div v-else-if="proxies.length === 0" class="empty-state">
        <p>No proxies configured</p>
        <button @click="showAddProxy = true" class="btn btn-secondary">
          Add Your First Proxy
        </button>
      </div>
      
      <!-- Proxy Cards -->
      <div v-else class="proxy-list">
        <div
          v-for="proxy in sortedProxies"
          :key="proxy.id"
          class="proxy-card"
          :class="{ disabled: !proxy.enabled }"
        >
          <!-- Header -->
          <div class="proxy-header">
            <div class="proxy-info">
              <span class="proxy-priority">Priority {{ proxy.priority }}</span>
              <span class="proxy-url">{{ maskPassword(proxy.proxy_url) }}</span>
            </div>
            
            <div class="proxy-badges">
              <span
                class="health-badge"
                :class="`health-${proxy.health_status}`"
              >
                {{ healthBadgeText(proxy.health_status) }}
              </span>
              
              <span v-if="!proxy.enabled" class="badge badge-secondary">
                Disabled
              </span>
            </div>
          </div>
          
          <!-- Stats -->
          <div class="proxy-stats">
            <div class="stat-item">
              <span class="stat-label">Response Time:</span>
              <span class="stat-value">
                {{ proxy.average_response_time_ms || 'N/A' }}
                <span v-if="proxy.average_response_time_ms">ms</span>
              </span>
            </div>
            
            <div class="stat-item">
              <span class="stat-label">Success Rate:</span>
              <span class="stat-value">
                {{ formatSuccessRate(proxy.success_rate) }}
              </span>
            </div>
            
            <div class="stat-item">
              <span class="stat-label">Consecutive Failures:</span>
              <span class="stat-value" :class="{ 'text-danger': proxy.consecutive_failures > 0 }">
                {{ proxy.consecutive_failures }}
              </span>
            </div>
            
            <div class="stat-item">
              <span class="stat-label">Total Recordings:</span>
              <span class="stat-value">
                {{ proxy.total_recordings }}
              </span>
            </div>
          </div>
          
          <!-- Last Check -->
          <div v-if="proxy.last_health_check" class="proxy-meta">
            <span class="meta-label">Last checked:</span>
            <span class="meta-value">{{ formatTimestamp(proxy.last_health_check) }}</span>
          </div>
          
          <!-- Actions -->
          <div class="proxy-actions">
            <button
              @click="handleTestProxy(proxy.id)"
              :disabled="testingProxyId === proxy.id"
              class="btn btn-sm btn-secondary"
            >
              {{ testingProxyId === proxy.id ? 'Testing...' : 'Test Now' }}
            </button>
            
            <button
              @click="handleToggleProxy(proxy.id)"
              class="btn btn-sm"
              :class="proxy.enabled ? 'btn-warning' : 'btn-success'"
            >
              {{ proxy.enabled ? 'Disable' : 'Enable' }}
            </button>
            
            <button
              @click="handleRemoveProxy(proxy.id)"
              class="btn btn-sm btn-danger"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Advanced Settings -->
    <div v-if="config.enable_proxy" class="advanced-settings">
      <h3>Advanced Proxy Settings</h3>
      
      <div class="form-group">
        <label class="checkbox-label">
          <input
            type="checkbox"
            v-model="config.proxy_health_check_enabled"
            @change="updateProxyConfig"
          />
          <span>Enable automatic health checks</span>
        </label>
        <p class="help-text">
          Periodically test proxy connectivity to detect failures automatically.
        </p>
      </div>
      
      <div v-if="config.proxy_health_check_enabled" class="form-group">
        <label class="form-label">Health Check Interval (seconds)</label>
        <input
          type="number"
          v-model.number="config.proxy_health_check_interval_seconds"
          min="60"
          max="3600"
          step="60"
          @change="updateProxyConfig"
          class="form-input"
        />
        <p class="help-text">
          How often to check proxy health (default: 300 seconds / 5 minutes).
        </p>
      </div>
      
      <div class="form-group">
        <label class="form-label">Max Consecutive Failures</label>
        <input
          type="number"
          v-model.number="config.proxy_max_consecutive_failures"
          min="1"
          max="10"
          @change="updateProxyConfig"
          class="form-input"
        />
        <p class="help-text">
          Auto-disable proxy after this many consecutive failures (default: 3).
        </p>
      </div>
      
      <div class="form-group">
        <label class="checkbox-label">
          <input
            type="checkbox"
            v-model="config.fallback_to_direct_connection"
            @change="updateProxyConfig"
          />
          <span>Fallback to direct connection if all proxies fail</span>
        </label>
        <p class="help-text">
          When enabled, recordings will continue without proxy if all proxies are down.
          <strong>Recommended:</strong> Keep enabled to prevent recording failures.
        </p>
      </div>
    </div>
    
    <!-- Add Proxy Modal -->
    <div v-if="showAddProxy" class="modal-overlay" @click.self="showAddProxy = false">
      <div class="modal-card">
        <div class="modal-header">
          <h3>Add New Proxy</h3>
          <button @click="showAddProxy = false" class="btn-close">×</button>
        </div>
        
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">Proxy URL</label>
            <input
              v-model="newProxyUrl"
              type="text"
              placeholder="http://username:password@proxy.example.com:9999"
              class="form-input"
              @keyup.enter="handleAddProxy"
            />
            <p class="help-text">
              Format: <code>http://[user:pass@]host:port</code>
            </p>
          </div>
          
          <div class="form-group">
            <label class="form-label">Priority</label>
            <input
              v-model.number="newProxyPriority"
              type="number"
              min="0"
              max="100"
              class="form-input"
            />
            <p class="help-text">
              Lower numbers = higher priority (0 = highest priority).
            </p>
          </div>
        </div>
        
        <div class="modal-footer">
          <button @click="showAddProxy = false" class="btn btn-secondary">
            Cancel
          </button>
          <button
            @click="handleAddProxy"
            :disabled="!newProxyUrl || isAddingProxy"
            class="btn btn-primary"
          >
            {{ isAddingProxy ? 'Adding...' : 'Add Proxy' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useProxySettings } from '@/composables/useProxySettings'

const {
  proxies,
  sortedProxies,
  config,
  healthyProxyCount,
  proxySystemStatus,
  isLoading,
  addProxy,
  removeProxy,
  testProxy,
  toggleProxy,
  updateConfig
} = useProxySettings()

const showAddProxy = ref(false)
const newProxyUrl = ref('')
const newProxyPriority = ref(0)
const isAddingProxy = ref(false)
const testingProxyId = ref<number | null>(null)

function maskPassword(url: string): string {
  try {
    const urlObj = new URL(url)
    if (urlObj.password) {
      urlObj.password = '***'
    }
    return urlObj.toString()
  } catch {
    return url  // Return as-is if not valid URL
  }
}

function healthBadgeText(status: string): string {
  const badges = {
    healthy: '✅ Healthy',
    degraded: '⚠️ Degraded',
    failed: '❌ Failed',
    unknown: '❓ Unknown'
  }
  return badges[status] || status
}

function formatSuccessRate(rate: number | null): string {
  if (rate === null || rate === undefined) return 'N/A'
  return `${(rate * 100).toFixed(1)}%`
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`
  
  return date.toLocaleString()
}

async function handleAddProxy() {
  if (!newProxyUrl.value) return
  
  isAddingProxy.value = true
  
  const result = await addProxy(newProxyUrl.value, newProxyPriority.value)
  
  if (result.success) {
    // Reset form
    newProxyUrl.value = ''
    newProxyPriority.value = 0
    showAddProxy.value = false
  } else {
    alert(`Failed to add proxy: ${result.error}`)
  }
  
  isAddingProxy.value = false
}

async function handleTestProxy(proxyId: number) {
  testingProxyId.value = proxyId
  
  const result = await testProxy(proxyId)
  
  // Show result toast/notification
  const statusEmoji = result.status === 'healthy' ? '✅' : result.status === 'degraded' ? '⚠️' : '❌'
  console.log(`${statusEmoji} Proxy test: ${result.status} (${result.response_time_ms}ms)`)
  
  testingProxyId.value = null
}

async function handleToggleProxy(proxyId: number) {
  await toggleProxy(proxyId)
}

async function handleRemoveProxy(proxyId: number) {
  if (!confirm('Remove this proxy? This action cannot be undone.')) {
    return
  }
  
  const result = await removeProxy(proxyId)
  
  if (!result.success) {
    alert(`Failed to remove proxy: ${result.error}`)
  }
}

async function updateProxyConfig() {
  await updateConfig(config.value)
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.proxy-settings-panel {
  padding: v.$spacing-4;
}

.system-status {
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  padding: v.$spacing-3;
  border-radius: v.$border-radius-md;
  margin-bottom: v.$spacing-4;
  border-left: 4px solid;
  
  &.status-healthy {
    background: rgba(var(--success-color-rgb), 0.1);
    border-color: var(--success-color);
  }
  
  &.status-degraded {
    background: rgba(var(--warning-color-rgb), 0.1);
    border-color: var(--warning-color);
  }
  
  &.status-error {
    background: rgba(var(--danger-color-rgb), 0.1);
    border-color: var(--danger-color);
  }
  
  &.status-disabled {
    background: var(--bg-secondary);
    border-color: var(--border-color);
  }
  
  .status-icon {
    font-size: 2rem;
  }
  
  .status-message {
    h4 {
      margin-bottom: v.$spacing-1;
      font-size: 1rem;
    }
    
    p {
      color: var(--text-secondary);
      font-size: 0.875rem;
    }
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: v.$spacing-3;
}

.proxy-list {
  display: grid;
  gap: v.$spacing-3;
}

.proxy-card {
  padding: v.$spacing-3;
  border: 2px solid var(--border-color);
  border-radius: v.$border-radius-md;
  transition: all 0.2s ease;
  
  &.disabled {
    opacity: 0.6;
    border-style: dashed;
  }
}

.proxy-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: v.$spacing-3;
  
  .proxy-info {
    display: flex;
    flex-direction: column;
    gap: v.$spacing-1;
    
    .proxy-priority {
      font-size: 0.75rem;
      color: var(--text-secondary);
      text-transform: uppercase;
    }
    
    .proxy-url {
      font-family: monospace;
      font-size: 0.875rem;
    }
  }
  
  .proxy-badges {
    display: flex;
    gap: v.$spacing-2;
    
    .health-badge {
      padding: 4px 8px;
      border-radius: v.$border-radius-sm;
      font-size: 0.75rem;
      font-weight: 600;
      
      &.health-healthy {
        background: rgba(var(--success-color-rgb), 0.2);
        color: var(--success-color);
      }
      
      &.health-degraded {
        background: rgba(var(--warning-color-rgb), 0.2);
        color: var(--warning-color);
      }
      
      &.health-failed {
        background: rgba(var(--danger-color-rgb), 0.2);
        color: var(--danger-color);
      }
      
      &.health-unknown {
        background: var(--bg-secondary);
        color: var(--text-secondary);
      }
    }
  }
}

.proxy-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: v.$spacing-2;
  margin-bottom: v.$spacing-3;
  padding: v.$spacing-2;
  background: var(--bg-secondary);
  border-radius: v.$border-radius-sm;
  
  .stat-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    
    .stat-label {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }
    
    .stat-value {
      font-weight: 600;
      
      &.text-danger {
        color: var(--danger-color);
      }
    }
  }
}

.proxy-meta {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: v.$spacing-2;
}

.proxy-actions {
  display: flex;
  gap: v.$spacing-2;
  flex-wrap: wrap;
}

.empty-state {
  text-align: center;
  padding: v.$spacing-6;
  color: var(--text-secondary);
  
  p {
    margin-bottom: v.$spacing-3;
  }
}

.advanced-settings {
  margin-top: v.$spacing-4;
  padding-top: v.$spacing-4;
  border-top: 1px solid var(--border-color);
  
  h3 {
    margin-bottom: v.$spacing-3;
    font-size: 1.1rem;
  }
}

// Modal styles
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-card {
  background: var(--bg-primary);
  border-radius: v.$border-radius-lg;
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: v.$spacing-4;
  border-bottom: 1px solid var(--border-color);
  
  h3 {
    margin: 0;
  }
  
  .btn-close {
    background: none;
    border: none;
    font-size: 2rem;
    cursor: pointer;
    color: var(--text-secondary);
    
    &:hover {
      color: var(--text-primary);
    }
  }
}

.modal-body {
  padding: v.$spacing-4;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: v.$spacing-2;
  padding: v.$spacing-4;
  border-top: 1px solid var(--border-color);
}
</style>
```
```vue
<template>
  <div class="proxy-settings">
    <h3>Proxy Configuration</h3>
    
    <div class="proxy-toggle">
      <label>
        <input type="checkbox" v-model="settings.enable_proxy" />
        Enable HTTP Proxy for Recordings
      </label>
    </div>
    
    <div v-if="settings.enable_proxy">
      <div class="proxy-list">
        <div v-for="proxy in proxies" :key="proxy.id" class="proxy-card">
          <div class="proxy-header">
            <span class="proxy-url">{{ maskPassword(proxy.proxy_url) }}</span>
            <span class="health-badge" :class="proxy.health_status">
              {{ proxy.health_status }}
            </span>
          </div>
          
          <div class="proxy-stats">
            <span>Response: {{ proxy.average_response_time_ms }}ms</span>
            <span>Success Rate: {{ (proxy.success_rate * 100).toFixed(1) }}%</span>
            <span>Failures: {{ proxy.consecutive_failures }}</span>
          </div>
          
          <div class="proxy-actions">
            <button @click="testProxy(proxy.id)">Test Now</button>
            <button @click="toggleProxy(proxy.id)">
              {{ proxy.enabled ? 'Disable' : 'Enable' }}
            </button>
            <button @click="deleteProxy(proxy.id)" class="danger">Delete</button>
          </div>
        </div>
      </div>
      
      <div class="add-proxy">
        <h4>Add New Proxy</h4>
        <input 
          v-model="newProxyUrl" 
          placeholder="http://user:pass@proxy.example.com:9999"
        />
        <button @click="addProxy">Add Proxy</button>
      </div>
      
      <div class="proxy-options">
        <label>
          <input type="checkbox" v-model="settings.fallback_to_direct_connection" />
          Fallback to direct connection if all proxies fail
        </label>
      </div>
    </div>
  </div>
</template>
```

**Health Check Performance**:
- Each health check: ~200-500ms (simple HTTP request)
- Interval: 5 minutes (configurable)
- Impact: Negligible - runs in background

**Benefits**:
1. ✅ Automatic failover to working proxy
2. ✅ No manual intervention when proxy fails
3. ✅ Statistics for proxy performance monitoring
4. ✅ Direct connection fallback (no recordings lost)
5. ✅ Priority-based proxy selection

**Migration Path**:
1. Deploy new code (backward compatible)
2. Run migration 025 (creates proxy_settings table)
3. Migrate existing proxy to new table:
   ```sql
   INSERT INTO proxy_settings (proxy_url, priority, enabled)
   SELECT proxy, 0, TRUE FROM recording_settings WHERE proxy IS NOT NULL;
   ```
4. Frontend auto-detects new proxy system

---

### 3. Streamlink Recovery on Proxy Failure

**Status**: 📝 Documented - Ready for Implementation  
**Priority**: HIGH (prevents recording loss on proxy failure)  
**Breaking Changes**: None

#### Background

**Current Behavior**:
- Streamlink process fails when proxy returns 500 error
- Recording marked as failed
- Stream data lost from failure point onwards

**Desired Behavior**:
- Detect proxy failure mid-recording
- Switch to next available proxy (or direct connection)
- Restart Streamlink process seamlessly
- Create new segment file
- Merge all segments at end of recording

#### Streamlink Segment Behavior

**Existing Segment System** (from code analysis):
```
Active Recording Structure:
/recordings/
  streamer_name_2025-11-12_10-55-23_segments/
    ├── segment_001.ts  (proxy 1)
    ├── segment_002.ts  (proxy 1)
    ├── segment_003.ts  (FAILED - proxy error)
    └── [recovery creates segment_004.ts with new proxy]

After Merge:
/recordings/
  streamer_name_2025-11-12_10-55-23.ts  (all segments combined)
```

**Current Segment Logic** (from `app/services/recording/process_manager.py`):
- Segments created in `_segments/` directory
- Named: `segment_NNN.ts`
- Merged after recording completes
- **Already supports multiple segment files!**

#### Implementation Plan

**1. Proxy Failure Detection**:

Add monitoring to `ProcessManager` to detect Streamlink failures:

```python
# app/services/recording/process_manager.py

async def _monitor_streamlink_process(self, process, recording_id, streamer_name):
    """Monitor Streamlink output for proxy failures"""
    
    while True:
        line = await process.stdout.readline()
        if not line:
            break  # Process ended
        
        log_line = line.decode('utf-8', errors='ignore')
        
        # Check for proxy-specific errors
        if 'ProxyError' in log_line or '500 Internal Server Error' in log_line:
            logger.error(f"🚨 Proxy failure detected for {streamer_name}: {log_line}")
            
            # Trigger recovery
            await self._handle_proxy_failure(recording_id, streamer_name)
            break
        
        # Check for other fatal errors
        if 'Failed to open stream' in log_line or 'Unable to open URL' in log_line:
            logger.error(f"❌ Stream failure for {streamer_name}: {log_line}")
            # Could be proxy or other issue - try recovery
            await self._handle_proxy_failure(recording_id, streamer_name)
            break
```

**2. Proxy Failover Logic**:

```python
async def _handle_proxy_failure(self, recording_id: int, streamer_name: str):
    """
    Handle proxy failure during active recording
    
    Steps:
    1. Mark current segment as incomplete
    2. Get next available proxy
    3. Restart Streamlink with new proxy
    4. Create new segment file
    """
    
    logger.warning(f"⚠️ Initiating proxy failover for {streamer_name}")
    
    # Get current recording state
    with SessionLocal() as db:
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            logger.error(f"Recording {recording_id} not found")
            return
        
        # Get next proxy
        from app.services.proxy.proxy_health_service import ProxyHealthService
        proxy_service = ProxyHealthService()
        
        # Mark current proxy as failed
        if recording.current_proxy_id:
            current_proxy = db.query(ProxySettings).filter(
                ProxySettings.id == recording.current_proxy_id
            ).first()
            if current_proxy:
                current_proxy.consecutive_failures += 1
                current_proxy.failed_recordings += 1
                db.commit()
        
        # Get next best proxy
        next_proxy_url = await proxy_service.get_best_proxy()
        
        # Log failover decision
        if next_proxy_url:
            logger.info(f"🔄 Switching to new proxy: {next_proxy_url}")
        else:
            logger.warning(f"⚠️ No healthy proxies - using direct connection")
        
        # Kill existing Streamlink process
        if recording_id in self.active_processes:
            process = self.active_processes[recording_id]
            process.terminate()
            await asyncio.sleep(2)  # Wait for graceful shutdown
            if process.poll() is None:  # Still running
                process.kill()
            
            # Clean up
            self.active_processes.pop(recording_id, None)
        
        # Increment segment counter
        recording.segment_number = (recording.segment_number or 0) + 1
        db.commit()
        
        # Restart recording with new proxy
        await self._restart_recording_with_proxy(
            recording_id=recording_id,
            streamer_name=streamer_name,
            proxy_url=next_proxy_url,
            segment_number=recording.segment_number
        )
```

**3. Seamless Restart**:

```python
async def _restart_recording_with_proxy(
    self,
    recording_id: int,
    streamer_name: str,
    proxy_url: Optional[str],
    segment_number: int
):
    """Restart Streamlink process with new proxy"""
    
    logger.info(f"🔄 Restarting recording for {streamer_name} (segment {segment_number})")
    
    with SessionLocal() as db:
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            return
        
        # Build new segment filename
        base_path = Path(recording.recording_path.replace('_segments', ''))
        segments_dir = base_path.parent / f"{base_path.stem}_segments"
        new_segment_file = segments_dir / f"segment_{segment_number:03d}.ts"
        
        # Build Streamlink command with new proxy
        command = self._build_streamlink_command(
            streamer_name=streamer_name,
            output_file=str(new_segment_file),
            quality='best',
            proxy_url=proxy_url  # NEW PROXY!
        )
        
        # Start new process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=os.environ.copy()
        )
        
        # Store process
        self.active_processes[recording_id] = process
        
        # Update recording state
        recording.current_proxy_id = await self._get_proxy_id_from_url(proxy_url, db)
        recording.recovery_attempts = (recording.recovery_attempts or 0) + 1
        recording.last_recovery_timestamp = datetime.now(timezone.utc)
        db.commit()
        
        # Monitor new process
        asyncio.create_task(
            self._monitor_streamlink_process(process, recording_id, streamer_name)
        )
        
        logger.info(f"✅ Recording restarted for {streamer_name} with segment {segment_number}")
```

**4. Database Schema Updates**:

```python
# Migration: 026_add_recovery_tracking.py

class Recording(Base):
    # ... existing fields ...
    
    # NEW: Recovery tracking
    segment_number = Column(Integer, default=0)           # Current segment number
    current_proxy_id = Column(Integer, ForeignKey('proxy_settings.id'))
    recovery_attempts = Column(Integer, default=0)        # How many times recovered
    last_recovery_timestamp = Column(DateTime(timezone=True))
    recovery_reason = Column(String)                      # "proxy_failure" | "network_error" etc.
```

**5. Segment Merging** (Already Exists):

The existing segment merging logic in `process_manager.py` already handles multiple segments:

```python
# Existing code (no changes needed):
async def _merge_segments(self, segments_dir: Path, output_file: Path):
    """Merge all segment files into final recording"""
    
    segment_files = sorted(segments_dir.glob("segment_*.ts"))
    
    if not segment_files:
        logger.error(f"No segments found in {segments_dir}")
        return False
    
    logger.info(f"📦 Merging {len(segment_files)} segments into {output_file}")
    
    # FFmpeg concatenation
    concat_file = segments_dir / "concat_list.txt"
    with open(concat_file, 'w') as f:
        for seg in segment_files:
            f.write(f"file '{seg.absolute()}'\n")
    
    ffmpeg_command = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(concat_file),
        '-c', 'copy',
        str(output_file)
    ]
    
    result = subprocess.run(ffmpeg_command, capture_output=True)
    
    if result.returncode == 0:
        logger.info(f"✅ Successfully merged segments to {output_file}")
        # Clean up segments directory
        shutil.rmtree(segments_dir)
        return True
    else:
        logger.error(f"❌ FFmpeg merge failed: {result.stderr.decode()}")
        return False
```

**This already works!** No changes needed for merging.

#### Recovery Flow Diagram

```
1. Recording Active (segment_001.ts)
   ↓
2. Proxy Failure Detected
   ↓
3. Get Next Proxy / Direct Connection
   ↓
4. Kill Streamlink Process
   ↓
5. Increment segment_number (2)
   ↓
6. Start New Streamlink (segment_002.ts)
   ↓
7. Continue Recording
   ↓
8. Stream Ends
   ↓
9. Merge All Segments → final.ts
   ↓
10. Clean Up _segments/ Directory
```

#### Recovery Limits

To prevent infinite retry loops:

```python
MAX_RECOVERY_ATTEMPTS = 5  # Maximum recoveries per recording

if recording.recovery_attempts >= MAX_RECOVERY_ATTEMPTS:
    logger.error(f"❌ Max recovery attempts reached for {streamer_name}")
    recording.status = 'failed'
    recording.error_message = 'Exceeded maximum recovery attempts'
    db.commit()
    return  # Give up
```

#### Testing Strategy

1. **Simulate Proxy Failure**:
   - Start recording with working proxy
   - Stop proxy service mid-recording
   - Verify automatic failover
   - Verify new segment created
   - Verify final merge successful

2. **Multiple Failovers**:
   - Configure 3 proxies
   - Fail them one by one
   - Verify recording continues
   - Verify all segments merged

3. **Direct Connection Fallback**:
   - Fail all proxies
   - Verify direct connection used
   - Verify recording completes

4. **Edge Cases**:
   - Proxy fails immediately (< 10s)
   - Proxy fails after hours
   - All proxies fail simultaneously
   - Recovery during stream end

#### Benefits

1. ✅ **No Recording Loss**: Stream continues despite proxy failures
2. ✅ **Automatic Recovery**: Zero manual intervention required
3. ✅ **Transparent to User**: Final .ts file looks like normal recording
4. ✅ **Statistics Tracking**: Know which proxies fail most often
5. ✅ **Fail-Safe**: Direct connection fallback prevents total failure

---

## 📝 **Implementation Order**

### **Priority Order (Status Update - Nov 12, 2025)**

1. ✅ **H.265/AV1 Support** (COMPLETED - Commits: b219ad1e, c415ec28, da591a46, 7aba76ce, 820032de)
   - ✅ Migration 024 applied
   - ✅ Backend: constants.py, models.py, streamlink_utils.py, process_manager.py
   - ✅ Frontend: RecordingSettingsPanel.vue, types/recording.ts
   - ⏸️ **Needs Testing**: Test with h264/h265/av1 streams

2. ✅ **Apprise Integration (Recording Events)** (COMPLETED - Commit: TBD)
   - ✅ Migration 027 applied (error tracking)
   - ✅ Migration 028 applied (notification settings)
   - ✅ Database schema ready
   - ✅ Frontend UI complete (NotificationSettingsPanel.vue)
   - ✅ Backend integration complete (process_manager.py)
   - ⏸️ **Needs Testing**: Test with ntfy/Discord notifications

3. ✅ **Stream Recovery After Restart** (COMPLETED - Commit: 82432f47)
   - ✅ Smart zombie cleanup with Twitch API check
   - ✅ Resume recording if streamer still live
   - ⏸️ **Needs Testing**: Test app restart during active recording

4. ✅ **Video Player Routing** (COMPLETED - Commit: 1752760a)
   - ✅ Fixed /videos/:id → /streamer/:streamerId/stream/:streamId/watch
   - ✅ VideoCard and VideosView updated
   - ⏸️ **Needs Testing**: Test video playback

5. 📝 **Recording Failure Detection** (NOT IMPLEMENTED)
   - **Problem**: Frontend shows "Recording" but Streamlink failed silently
   - **Impact**: User thinks recording works, but no data is saved
   - **Estimated Time**: 30-60 minutes
   - **Blocker**: Needs WebSocket + Toast system

6. 📝 **Multi-Proxy System** (NOT IMPLEMENTED)
   - **Priority**: CRITICAL (current proxy DOWN)
   - **Complexity**: High (3-4 hours)
   - **Requires**: Health check system, database migration

7. 📝 **Streamlink Recovery on Proxy Failure** (NOT IMPLEMENTED)
   - **Builds on**: Multi-proxy system
   - **Estimated Time**: 1-2 hours
   - **Uses**: Existing segment merge logic

8. 📝 **Settings UI Feedback (Toast System)** (NOT IMPLEMENTED)
   - **Impact**: Better UX for save operations
   - **Estimated Time**: 30 minutes
   - **Dependency**: Toast notification component

**Completion Status**: 5/8 features complete (62.5%)  
**Testing Required**: H.265/AV1, Apprise, Stream Recovery, Video Player

---

## 7. Apprise Integration for Recording Events

**Status**: ✅ **COMPLETED**  
**Implementation**: 
- ✅ Migration 027 (error tracking) - Applied
- ✅ Migration 028 (notification settings) - Applied
- ✅ Frontend UI (NotificationSettingsPanel.vue) - Lines 59-75, 234-236, 352-354
- ✅ Backend integration (process_manager.py) - Lines 330, 573, 711, 1169
**Testing Status**: ⏸️ Needs End-to-End Testing with Apprise services

### Implementation Summary

**Frontend (NotificationSettingsPanel.vue):**
- Checkboxes: `notifyRecordingStarted`, `notifyRecordingFailed`, `notifyRecordingCompleted`
- Data ref: Initialized with correct defaults (Failed = ON by default)
- SaveSettings: Emits all 3 fields to backend

**Backend (process_manager.py):**
- `_start_segment()` (line 330): Sends `recording_started` notification
- `wait_for_process()` (line 573): Sends `recording_completed` for non-segmented recordings
- `_finalize_segmented_recording()` (line 711): Sends `recording_completed` for segmented recordings
- `_notify_recording_failed()` (line 1169): Sends `recording_failed` notification

**External Service (external_notification_service.py):**
- `send_recording_notification()` method already implemented (line 300)
- Checks GlobalSettings for event-specific toggles
- Supports 100+ services via Apprise

### Current Apprise Infrastructure (Already Implemented)

**File: `app/services/notifications/external_notification_service.py`**
- Supports 100+ services: Discord, Telegram, Ntfy, Pushover, Slack, Matrix, etc.
- Methods:
  - `send_notification(message, title)` - Basic notifications
  - `send_stream_notification(streamer_name, event_type, details)` - Stream events (online/offline/update)
  - `send_test_notification()` - Test button
  - `_get_service_specific_url(...)` - Service-specific configuration (ntfy, discord, telegram, etc.)

**Current Event Types:**
- `online` - Streamer went live
- `offline` - Streamer went offline
- `update` - Stream title/category changed
- `favorite_category` - Streamer started favorite category

**GlobalSettings Model (app/models.py):**
```python
class GlobalSettings(Base):
    notification_url: Optional[str]
    notifications_enabled: bool
    notify_online_global: bool
    notify_offline_global: bool
    notify_update_global: bool
    notify_favorite_category_global: bool
```

### Extension Strategy

#### 1. New Event Types for Recording Events
Add support for 3 new event types:
- `recording_started` - Recording successfully started
- `recording_failed` - Recording failed (Streamlink crash, proxy error, etc.)
- `recording_completed` - Recording finished successfully

#### 2. Migration 028 - System Notification Settings

**File: `migrations/028_add_system_notification_settings.py`**

```python
"""Add system notification settings for recording events"""

from sqlalchemy import Boolean, Column, Integer, String, text
from app.database import SessionLocal, engine, Base

def upgrade():
    """Add notification preferences for recording events"""
    with SessionLocal() as db:
        try:
            # Add new columns to global_settings
            db.execute(text("""
                ALTER TABLE global_settings
                ADD COLUMN IF NOT EXISTS notify_recording_started BOOLEAN DEFAULT false,
                ADD COLUMN IF NOT EXISTS notify_recording_failed BOOLEAN DEFAULT true,
                ADD COLUMN IF NOT EXISTS notify_recording_completed BOOLEAN DEFAULT false;
            """))
            
            db.commit()
            print("✅ Added system notification settings")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Migration failed: {e}")
            raise

def downgrade():
    """Remove system notification settings"""
    with SessionLocal() as db:
        try:
            db.execute(text("""
                ALTER TABLE global_settings
                DROP COLUMN IF EXISTS notify_recording_started,
                DROP COLUMN IF EXISTS notify_recording_failed,
                DROP COLUMN IF EXISTS notify_recording_completed;
            """))
            
            db.commit()
            print("✅ Removed system notification settings")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Downgrade failed: {e}")
            raise

if __name__ == "__main__":
    upgrade()
```

#### 3. Update GlobalSettings Model

**File: `app/models.py`**

```python
class GlobalSettings(Base):
    __tablename__ = "global_settings"
    
    # ... existing fields ...
    notification_url: Optional[str] = Column(String)
    notifications_enabled: bool = Column(Boolean, default=True)
    notify_online_global: bool = Column(Boolean, default=True)
    notify_offline_global: bool = Column(Boolean, default=True)
    notify_update_global: bool = Column(Boolean, default=True)
    notify_favorite_category_global: bool = Column(Boolean, default=True)
    
    # NEW: System notification settings (recording events)
    notify_recording_started: bool = Column(Boolean, default=False)  # Default: OFF (noisy)
    notify_recording_failed: bool = Column(Boolean, default=True)    # Default: ON (critical)
    notify_recording_completed: bool = Column(Boolean, default=False) # Default: OFF (noisy)
```

**Rationale for defaults:**
- `recording_started` → OFF: Every live stream triggers recording, too noisy
- `recording_failed` → ON: Critical issue user needs to know immediately
- `recording_completed` → OFF: Most recordings complete normally, noisy

#### 4. Extend ExternalNotificationService

**File: `app/services/notifications/external_notification_service.py`**

Add new method after `send_stream_notification()`:

```python
async def send_recording_notification(self, streamer_name: str, event_type: str, 
                                     details: dict = None) -> bool:
    """
    Send notification for recording events (started/failed/completed)
    
    Args:
        streamer_name: Name of the streamer
        event_type: 'recording_started', 'recording_failed', 'recording_completed'
        details: Additional info (error_message, duration, file_size, etc.)
    
    Returns:
        True if notification sent successfully
    """
    try:
        if not self._notifications_enabled:
            logger.debug("Notifications globally disabled")
            return False
        
        if not self._notification_url:
            logger.debug("No notification URL configured")
            return False
        
        # Check if this specific event type is enabled
        with SessionLocal() as db:
            settings = db.query(GlobalSettings).first()
            if not settings:
                logger.debug("No global settings found")
                return False
            
            # Check event-specific toggle
            if event_type == "recording_started" and not settings.notify_recording_started:
                logger.debug("Recording started notifications disabled")
                return False
            elif event_type == "recording_failed" and not settings.notify_recording_failed:
                logger.debug("Recording failed notifications disabled")
                return False
            elif event_type == "recording_completed" and not settings.notify_recording_completed:
                logger.debug("Recording completed notifications disabled")
                return False
            
            # Get streamer for profile image
            streamer = db.query(Streamer).filter(Streamer.username == streamer_name).first()
            if not streamer:
                logger.debug(f"Streamer {streamer_name} not found")
                return False
            
            # Get profile image URL (HTTP only)
            profile_image_url = ""
            if streamer.original_profile_image_url and streamer.original_profile_image_url.startswith('http'):
                profile_image_url = streamer.original_profile_image_url
            elif details and details.get("profile_image_url", "").startswith('http'):
                profile_image_url = details["profile_image_url"]
            
            twitch_url = f"https://twitch.tv/{streamer_name}"
            
            # Get service-specific URL
            notification_url = self._get_service_specific_url(
                base_url=settings.notification_url,
                twitch_url=twitch_url,
                profile_image=profile_image_url,
                streamer_name=streamer_name,
                event_type=event_type
            )
            
            # Create Apprise instance
            apprise = Apprise()
            if not apprise.add(notification_url):
                logger.error(f"Failed to add notification URL: {notification_url}")
                return False
            
            # Format message
            title, message = self.formatter.format_recording_notification(
                streamer_name=streamer_name,
                event_type=event_type,
                details=details or {}
            )
            
            # Send notification
            logger.debug(f"Sending recording notification: {event_type} for {streamer_name}")
            result = await apprise.async_notify(
                title=title,
                body=message,
                body_format=NotifyFormat.TEXT
            )
            
            if result:
                logger.info(f"✅ Recording notification sent: {event_type} - {streamer_name}")
            else:
                logger.error(f"❌ Failed to send recording notification: {event_type}")
            
            return result
    
    except Exception as e:
        logger.error(f"Error sending recording notification: {e}", exc_info=True)
        return False
```

#### 5. Extend NotificationFormatter

**File: `app/services/notifications/notification_formatter.py`**

Add new method:

```python
def format_recording_notification(self, streamer_name: str, event_type: str, 
                                 details: dict) -> tuple[str, str]:
    """Format recording event notifications"""
    
    if event_type == "recording_started":
        title = f"🔴 Recording Started: {streamer_name}"
        message = (
            f"Started recording {streamer_name}'s stream.\n\n"
            f"Quality: {details.get('quality', 'best')}\n"
            f"Title: {details.get('stream_title', 'N/A')}\n"
            f"Category: {details.get('category', 'N/A')}"
        )
    
    elif event_type == "recording_failed":
        title = f"❌ Recording Failed: {streamer_name}"
        error = details.get('error_message', 'Unknown error')
        message = (
            f"Recording failed for {streamer_name}.\n\n"
            f"Error: {error}\n"
            f"Time: {details.get('timestamp', 'N/A')}\n\n"
            f"Check logs for more details."
        )
    
    elif event_type == "recording_completed":
        title = f"✅ Recording Completed: {streamer_name}"
        duration = details.get('duration_minutes', 0)
        file_size_mb = details.get('file_size_mb', 0)
        message = (
            f"Recording completed for {streamer_name}.\n\n"
            f"Duration: {duration} minutes\n"
            f"File size: {file_size_mb} MB\n"
            f"Quality: {details.get('quality', 'best')}"
        )
    
    else:
        title = f"📹 Recording Event: {streamer_name}"
        message = f"Event: {event_type}"
    
    return title, message

def get_event_title_map(self) -> dict:
    """Get title map for all event types"""
    return {
        # Stream events
        "online": "is now live",
        "offline": "went offline",
        "update": "updated stream",
        "favorite_category": "started favorite category",
        # Recording events (NEW)
        "recording_started": "recording started",
        "recording_failed": "recording failed",
        "recording_completed": "recording completed"
    }
```

#### 6. Integrate with Process Manager

**File: `app/services/recording/process_manager.py`**

Update `_monitor_streamlink_process()` to send Apprise notifications:

```python
async def _monitor_streamlink_process(self, stream: Stream, process, recording_id: int):
    """Monitor Streamlink process with recording event notifications"""
    try:
        from app.services.notifications.external_notification_service import ExternalNotificationService
        notification_service = ExternalNotificationService()
        
        # ... existing monitoring code ...
        
        # CRITICAL: Detect process failure
        if process.returncode != 0:
            error_message = f"Streamlink exited with code {process.returncode}"
            logger.error(f"❌ {error_message}")
            
            # Update database
            with SessionLocal() as db:
                recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if recording:
                    recording.status = 'failed'
                    recording.error_message = error_message
                    recording.failure_timestamp = datetime.now(timezone.utc)
                    db.commit()
            
            # Broadcast WebSocket error
            await self._notify_recording_failed(stream, error_message)
            
            # Send Apprise notification (NEW)
            await notification_service.send_recording_notification(
                streamer_name=stream.streamer.username,
                event_type='recording_failed',
                details={
                    'error_message': error_message,
                    'timestamp': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'stream_title': stream.title or 'N/A',
                    'category': stream.category_name or 'N/A'
                }
            )
            
            return
    
    except Exception as e:
        logger.error(f"Error in process monitoring: {e}", exc_info=True)
```

Add notification on recording start:

```python
async def start_recording(self, stream: Stream, quality: str = "best") -> Optional[int]:
    """Start recording with notification"""
    try:
        # ... existing start logic ...
        
        if process and process.returncode is None:
            logger.info(f"✅ Recording started for {stream.streamer.username}")
            
            # Send Apprise notification (NEW)
            from app.services.notifications.external_notification_service import ExternalNotificationService
            notification_service = ExternalNotificationService()
            
            await notification_service.send_recording_notification(
                streamer_name=stream.streamer.username,
                event_type='recording_started',
                details={
                    'quality': quality,
                    'stream_title': stream.title or 'N/A',
                    'category': stream.category_name or 'N/A'
                }
            )
            
            return recording_id
    
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        return None
```

Add notification on completion:

```python
async def _finalize_recording(self, stream: Stream, recording_id: int):
    """Finalize recording with completion notification"""
    try:
        # ... existing finalization logic ...
        
        # Send completion notification (NEW)
        from app.services.notifications.external_notification_service import ExternalNotificationService
        notification_service = ExternalNotificationService()
        
        duration_minutes = int((recording.end_time - recording.start_time).total_seconds() / 60)
        file_size_mb = 0
        
        if recording.recording_path and os.path.exists(recording.recording_path):
            file_size_mb = round(os.path.getsize(recording.recording_path) / (1024 * 1024), 2)
        
        await notification_service.send_recording_notification(
            streamer_name=stream.streamer.username,
            event_type='recording_completed',
            details={
                'duration_minutes': duration_minutes,
                'file_size_mb': file_size_mb,
                'quality': recording.quality or 'best'
            }
        )
    
    except Exception as e:
        logger.error(f"Error finalizing recording: {e}", exc_info=True)
```

#### 7. Frontend - Extend NotificationSettingsPanel.vue

**File: `app/frontend/src/components/settings/NotificationSettingsPanel.vue`**

Add new section after streamer notifications:

```vue
<template>
  <div class="settings-panel">
    <!-- Existing: Global Notification Settings -->
    <div class="settings-section">
      <h3>Global Notification Settings</h3>
      <!-- ... existing notification URL, enabled toggle ... -->
    </div>

    <!-- NEW: System Notification Settings -->
    <div class="settings-section">
      <h3>System Notifications</h3>
      <p class="section-description">
        Configure which recording events trigger external notifications (Apprise).
      </p>
      
      <div class="notification-toggles">
        <div class="toggle-row">
          <label class="toggle-label">
            <input 
              type="checkbox" 
              v-model="systemSettings.notify_recording_started"
              @change="saveSystemSettings"
            />
            <span class="toggle-text">
              <strong>Recording Started</strong>
              <span class="help-text">Notify when recording begins (may be noisy)</span>
            </span>
          </label>
        </div>
        
        <div class="toggle-row critical">
          <label class="toggle-label">
            <input 
              type="checkbox" 
              v-model="systemSettings.notify_recording_failed"
              @change="saveSystemSettings"
            />
            <span class="toggle-text">
              <strong>Recording Failed ⚠️</strong>
              <span class="help-text">Notify when recording fails (RECOMMENDED)</span>
            </span>
          </label>
        </div>
        
        <div class="toggle-row">
          <label class="toggle-label">
            <input 
              type="checkbox" 
              v-model="systemSettings.notify_recording_completed"
              @change="saveSystemSettings"
            />
            <span class="toggle-text">
              <strong>Recording Completed</strong>
              <span class="help-text">Notify when recording finishes successfully</span>
            </span>
          </label>
        </div>
      </div>
    </div>

    <!-- Existing: Streamer Notification Settings -->
    <div class="settings-section">
      <h3>Streamer Notifications</h3>
      <!-- ... existing per-streamer toggles ... -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'

const toast = useToast()

interface SystemNotificationSettings {
  notify_recording_started: boolean
  notify_recording_failed: boolean
  notify_recording_completed: boolean
}

const systemSettings = ref<SystemNotificationSettings>({
  notify_recording_started: false,
  notify_recording_failed: true,
  notify_recording_completed: false
})

async function loadSystemSettings() {
  try {
    const response = await fetch('/api/settings', {
      credentials: 'include'
    })
    
    if (response.ok) {
      const data = await response.json()
      systemSettings.value = {
        notify_recording_started: data.notify_recording_started ?? false,
        notify_recording_failed: data.notify_recording_failed ?? true,
        notify_recording_completed: data.notify_recording_completed ?? false
      }
    }
  } catch (error) {
    console.error('Failed to load system notification settings:', error)
    toast.error('Failed to load notification settings')
  }
}

async function saveSystemSettings() {
  try {
    const response = await fetch('/api/settings', {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(systemSettings.value)
    })
    
    if (response.ok) {
      toast.success('System notification settings saved')
    } else {
      toast.error('Failed to save settings')
    }
  } catch (error) {
    console.error('Failed to save system notification settings:', error)
    toast.error('Failed to save settings')
  }
}

onMounted(() => {
  loadSystemSettings()
})
</script>

<style scoped lang="scss">
@use '@/styles/mixins' as m;
@use '@/styles/variables' as v;

.notification-toggles {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-3;
}

.toggle-row {
  padding: v.$spacing-3;
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: v.$border-radius;
  
  &.critical {
    border-left: 3px solid var(--danger-color);
  }
}

.toggle-label {
  display: flex;
  align-items: flex-start;
  gap: v.$spacing-3;
  cursor: pointer;
  
  input[type="checkbox"] {
    margin-top: 0.25rem;
  }
}

.toggle-text {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-1;
  
  strong {
    color: var(--text-primary);
    font-size: var(--text-base);
  }
}

.help-text {
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.section-description {
  color: var(--text-secondary);
  margin-bottom: v.$spacing-4;
}
</style>
```

#### 8. API Endpoint Updates

**File: `app/routes/settings.py`**

Update GET endpoint to include system notification settings:

```python
@router.get("")
async def get_settings(db: Session = Depends(get_db)):
    """Get global settings including system notification preferences"""
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings()
        db.add(settings)
        db.commit()
    
    return {
        # ... existing fields ...
        "notification_url": settings.notification_url,
        "notifications_enabled": settings.notifications_enabled,
        # NEW: System notification settings
        "notify_recording_started": settings.notify_recording_started,
        "notify_recording_failed": settings.notify_recording_failed,
        "notify_recording_completed": settings.notify_recording_completed
    }
```

Update PUT endpoint to save system notification settings:

```python
@router.put("")
async def update_settings(
    settings_data: dict,
    db: Session = Depends(get_db)
):
    """Update global settings including system notification preferences"""
    settings = db.query(GlobalSettings).first()
    if not settings:
        settings = GlobalSettings()
        db.add(settings)
    
    # ... existing field updates ...
    
    # NEW: Update system notification settings
    if "notify_recording_started" in settings_data:
        settings.notify_recording_started = settings_data["notify_recording_started"]
    if "notify_recording_failed" in settings_data:
        settings.notify_recording_failed = settings_data["notify_recording_failed"]
    if "notify_recording_completed" in settings_data:
        settings.notify_recording_completed = settings_data["notify_recording_completed"]
    
    db.commit()
    return {"message": "Settings updated successfully"}
```

### Testing Plan

**Apprise Integration Testing:**
- [ ] Enable `notify_recording_failed` → Start recording → Kill Streamlink → Verify Apprise notification sent
- [ ] Enable `notify_recording_started` → Force record → Verify notification sent
- [ ] Disable `notify_recording_failed` → Recording fails → Verify NO notification sent
- [ ] Test with ntfy, Discord, Telegram services
- [ ] Verify profile images appear in notifications (HTTP URLs only)
- [ ] Test notification formatting for all 3 event types
- [ ] Verify notifications work with existing stream notifications (no conflicts)

**Frontend Testing:**
- [ ] NotificationSettingsPanel displays system notification toggles
- [ ] Toggle switches persist after page refresh
- [ ] Default settings: started=OFF, failed=ON, completed=OFF
- [ ] Save operation shows success toast
- [ ] Settings API endpoint returns correct values

**Integration Testing:**
- [ ] Recording starts → Apprise notification → Toast notification (if enabled)
- [ ] Recording fails → WebSocket event → Apprise notification → Toast notification
- [ ] Recording completes → Apprise notification (if enabled)
- [ ] Multiple notification services (ntfy + Discord) both receive events

---

## 8. Testing & Validation

### ✅ Implemented Features Testing Checklist

**H.265/AV1 Codec Support:**
- [ ] Test with h264-only channel (most channels)
- [ ] Test with h265-capable channel (1440p streamer)
- [ ] Verify fallback to h264 when h265 not available
- [ ] Check file sizes (h265 = ~30% smaller than h264 at same quality)
- [ ] Test playback compatibility on various devices
- [ ] Verify codec dropdown in RecordingSettingsPanel
- [ ] Test save/load of codec preferences

**Stream Recovery After Restart:**
- [ ] Start recording → Restart app while streamer live → Verify recording resumes
- [ ] Start recording → Restart app after streamer offline → Verify marked as stopped
- [ ] Check logs for "🔄 RESUMING recording" vs "🛑 marking recording as stopped"
- [ ] Verify Twitch API connectivity check works
- [ ] Test with multiple zombie recordings
- [ ] Verify stream.ended_at set correctly for offline streams

**Video Player Routing:**
- [ ] Click video card → Verify navigation to /streamer/:streamerId/stream/:streamId/watch
- [ ] Click play button → Verify same navigation
- [ ] Verify VideoPlayerView loads with correct streamerId and streamId
- [ ] Test video playback controls work
- [ ] Verify query params (title, streamerName) passed correctly

**Apprise Recording Events (Backend Only - No Frontend Yet):**
- [ ] Verify Migration 027 applied: error_message, failure_reason, failure_timestamp columns exist
- [ ] Verify Migration 028 applied: notify_recording_started, notify_recording_failed, notify_recording_completed columns exist
- [ ] Check database default values: started=false, failed=true, completed=false
- [ ] Manually update notification settings in DB → Verify persists

### 📝 Not Implemented Features (Skip Testing)

**Recording Failure Detection:**
- ⏸️ NOT IMPLEMENTED - Skip until WebSocket + Toast system ready

**Toast System:**
- ⏸️ NOT IMPLEMENTED - Required for Recording Failure Detection

**Multi-Proxy System:**
- ⏸️ NOT IMPLEMENTED - Migration 025 not created

**Streamlink Recovery on Proxy Failure:**
- ⏸️ NOT IMPLEMENTED - Depends on Multi-Proxy

**Settings UI Feedback:**
- ⏸️ NOT IMPLEMENTED - Depends on Toast system

---

## 🚨 **CRITICAL FEATURE: Recording Failure Detection & Propagation**

**Status**: 📝 Documented - HIGHEST PRIORITY  
**Priority**: CRITICAL  
**Impact**: User sees "Recording Active" but no data is being saved

### Current Problem

**Symptom**:
- User clicks "Force Record"
- Frontend shows "🔴 Recording" badge
- Streamlink fails (proxy error, network issue, etc.)
- **Database still shows `status='recording'`**
- **Frontend keeps showing "Recording Active"**
- **No video data is actually saved**

**Root Cause**:
```python
# process_manager.py - Current behavior
def start_recording(streamer_name):
    # 1. Create Recording in DB with status='recording'
    recording = Recording(status='recording')
    db.commit()
    
    # 2. Start Streamlink process
    process = subprocess.Popen([...])
    
    # 3. If Streamlink fails after 1 minute:
    #    - Process exits with error
    #    - Database STILL shows status='recording'
    #    - Frontend STILL shows "Recording" 
    #    - NO ERROR MESSAGE sent to user!
```

**User Impact**: 
- ❌ User thinks recording works
- ❌ Streams for hours without data being saved
- ❌ Discovers failure only when checking files manually
- ❌ Lost streams can't be recovered

### Solution: Comprehensive Failure Detection

**Backend Changes** - See full implementation in document section below
**Frontend Changes** - Toast notifications + WebSocket error handling

---

## 🎨 **FEATURE: Settings UI Feedback Improvements**

**Status**: 📝 Documented  
**Priority**: MEDIUM  
**Impact**: Better user experience, clear action feedback

### Current Problem

**Symptom**:
- User clicks "Save Settings"
- Button text changes to "Saving..."
- Button text changes back to "Save Settings"
- **No confirmation that save succeeded**
- **No error message if save failed**
- **User clicks again thinking it didn't work**

### Solution: Toast Notifications + Visual Feedback

**Implementation** - See full code in document section below

---

## 🧪 **Testing Checklist**

### H.265/AV1:
- [ ] Test with h264-only channel
- [ ] Test with h265-capable channel (1440p)
- [ ] Verify fallback behavior
- [ ] Check file sizes (h265 should be ~30% smaller)
- [ ] Test playback on various devices

### Multi-Proxy:
- [ ] Add 2+ proxies
- [ ] Verify health check runs every 5 minutes
- [ ] Simulate proxy failure (stop proxy service)
- [ ] Verify automatic failover to next proxy
- [ ] Test direct connection fallback
- [ ] Verify recording continues without interruption

### Recording Failure Detection:
- [ ] Start recording → Kill Streamlink manually → Verify frontend shows "Failed"
- [ ] Start recording → Stop proxy → Verify error toast appears
- [ ] Simulate network error → Verify error logged to database
- [ ] Check logs show error messages properly
- [ ] Verify WebSocket sends failure notification
- [ ] Test error toast auto-dismiss after 10 seconds
- [ ] Test manual toast dismiss button
- [ ] Verify recording status badge updates to "Failed"
- [ ] Test "Details" button shows full error message

### Settings UI Feedback:
- [ ] Save settings → See success toast
- [ ] Save with network error → See error toast
- [ ] Button shows spinner during save
- [ ] Button disabled during save (can't double-click)
- [ ] Toast auto-dismisses after 5 seconds
- [ ] Multiple toasts stack properly
- [ ] Toast close button works

---

## 📋 **DETAILED IMPLEMENTATIONS**

### A. Recording Failure Detection (CRITICAL)

#### Backend Implementation

**File: `app/services/recording/process_manager.py`**

```python
async def _monitor_streamlink_process(
    self, 
    process, 
    recording_id: int, 
    streamer_name: str
):
    """
    Monitor Streamlink process for failures
    Send real-time updates to frontend via WebSocket
    """
    
    failure_detected = False
    error_messages = []
    
    # Monitor stdout/stderr
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        
        log_line = line.decode('utf-8', errors='ignore')
        logger.info(f"[{streamer_name}] {log_line}")
        
        # Detect critical errors
        if any(err in log_line for err in [
            'ProxyError',
            '500 Internal Server Error',
            'Failed to open stream',
            'Unable to open URL',
            'No playable streams found',
            'error: Unable to find'
        ]):
            failure_detected = True
            error_messages.append(log_line.strip())
            logger.error(f"🚨 Critical error for {streamer_name}: {log_line}")
    
    # Wait for process to exit
    return_code = await process.wait()
    
    # Handle process exit
    with SessionLocal() as db:
        recording = db.query(Recording).filter(Recording.id == recording_id).first()
        if not recording:
            return
        
        if return_code != 0 or failure_detected:
            # CRITICAL: Mark as FAILED
            recording.status = 'failed'
            recording.ended_at = datetime.now(timezone.utc)
            recording.error_message = '\n'.join(error_messages[-5:])  # Last 5 errors
            recording.failure_reason = self._classify_error(error_messages)
            recording.failure_timestamp = datetime.now(timezone.utc)
            db.commit()
            
            logger.error(f"❌ Recording FAILED for {streamer_name}: exit code {return_code}")
            
            # Send WebSocket notification to frontend
            await self._notify_recording_failed(
                recording_id=recording_id,
                streamer_name=streamer_name,
                error_message=recording.error_message
            )
            
            # Clean up process tracking
            self.active_processes.pop(recording_id, None)
            
        else:
            # Normal completion
            logger.info(f"✅ Recording completed successfully for {streamer_name}")
            recording.status = 'completed'
            recording.ended_at = datetime.now(timezone.utc)
            db.commit()


def _classify_error(self, error_messages: list) -> str:
    """Classify error type for statistics"""
    error_text = ' '.join(error_messages).lower()
    
    if 'proxyerror' in error_text or '500 internal server error' in error_text:
        return 'proxy_error'
    elif 'network' in error_text or 'timeout' in error_text:
        return 'network_error'
    elif 'no playable streams' in error_text:
        return 'stream_offline'
    elif 'unable to open url' in error_text:
        return 'url_error'
    else:
        return 'unknown_error'


async def _notify_recording_failed(
    self,
    recording_id: int,
    streamer_name: str,
    error_message: str
):
    """Send recording failure to all connected WebSocket clients"""
    
    from app.routes.websocket import connection_manager
    
    # Send failure notification
    await connection_manager.broadcast({
        'type': 'recording_failed',
        'data': {
            'recording_id': recording_id,
            'streamer_name': streamer_name,
            'error_message': error_message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    })
    
    # Also update active recordings list (remove failed recording)
    active_recordings = await self.get_active_recordings_status()
    await connection_manager.broadcast({
        'type': 'active_recordings_update',
        'data': {
            'active_recordings': active_recordings
        }
    })
```

**File: `migrations/027_add_recording_error_tracking.py`**

```python
"""Add error tracking columns to recordings table

Revision ID: 027
Revises: 026
Create Date: 2025-11-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.add_column('recordings', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('recordings', sa.Column('failure_reason', sa.String(50), nullable=True))
    op.add_column('recordings', sa.Column('failure_timestamp', sa.DateTime(timezone=True), nullable=True))
    op.add_column('recordings', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))

def downgrade():
    op.drop_column('recordings', 'retry_count')
    op.drop_column('recordings', 'failure_timestamp')
    op.drop_column('recordings', 'failure_reason')
    op.drop_column('recordings', 'error_message')
```

#### Frontend Implementation

**File: `app/frontend/src/composables/useToast.ts` (NEW)**

```typescript
import { ref } from 'vue'

interface Toast {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  title: string
  message: string
  duration: number
}

const toasts = ref<Toast[]>([])
let toastIdCounter = 0

export function useToast() {
  function showToast(
    type: Toast['type'],
    title: string,
    message: string,
    options: { duration?: number } = {}
  ) {
    const toast: Toast = {
      id: toastIdCounter++,
      type,
      title,
      message,
      duration: options.duration || 5000
    }
    
    toasts.value.push(toast)
    
    // Auto-remove after duration
    setTimeout(() => {
      removeToast(toast.id)
    }, toast.duration)
  }
  
  function showErrorToast(title: string, message: string, options = {}) {
    showToast('error', title, message, options)
  }
  
  function showSuccessToast(title: string, message: string, options = {}) {
    showToast('success', title, message, options)
  }
  
  function showWarningToast(title: string, message: string, options = {}) {
    showToast('warning', title, message, options)
  }
  
  function removeToast(id: number) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index !== -1) {
      toasts.value.splice(index, 1)
    }
  }
  
  return {
    toasts,
    showToast,
    showErrorToast,
    showSuccessToast,
    showWarningToast,
    removeToast
  }
}
```

**File: `app/frontend/src/components/ToastContainer.vue` (NEW)**

```vue
<template>
  <div class="toast-container">
    <TransitionGroup name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast"
        :class="`toast-${toast.type}`"
      >
        <div class="toast-icon">
          <span v-if="toast.type === 'error'">❌</span>
          <span v-else-if="toast.type === 'success'">✅</span>
          <span v-else-if="toast.type === 'warning'">⚠️</span>
          <span v-else>ℹ️</span>
        </div>
        
        <div class="toast-content">
          <h4 class="toast-title">{{ toast.title }}</h4>
          <p class="toast-message">{{ toast.message }}</p>
        </div>
        
        <button @click="removeToast(toast.id)" class="toast-close">×</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { toasts, removeToast } = useToast()
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;

.toast-container {
  position: fixed;
  top: 80px;  // Below navbar
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: v.$spacing-2;
  max-width: 400px;
  
  @media (max-width: 768px) {
    left: 20px;
    right: 20px;
    max-width: none;
  }
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: v.$spacing-3;
  padding: v.$spacing-3;
  border-radius: v.$border-radius-md;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(10px);
  
  &.toast-error {
    background: rgba(220, 38, 38, 0.95);
    border-left: 4px solid #dc2626;
    color: white;
  }
  
  &.toast-success {
    background: rgba(34, 197, 94, 0.95);
    border-left: 4px solid #22c55e;
    color: white;
  }
  
  &.toast-warning {
    background: rgba(251, 191, 36, 0.95);
    border-left: 4px solid #fbbf24;
    color: #1f2937;
  }
  
  &.toast-info {
    background: rgba(59, 130, 246, 0.95);
    border-left: 4px solid #3b82f6;
    color: white;
  }
}

.toast-icon {
  font-size: 1.5rem;
  flex-shrink: 0;
}

.toast-content {
  flex: 1;
  min-width: 0;
  
  .toast-title {
    margin: 0 0 v.$spacing-1 0;
    font-weight: 600;
    font-size: 0.95rem;
  }
  
  .toast-message {
    margin: 0;
    font-size: 0.875rem;
    opacity: 0.9;
    word-break: break-word;
  }
}

.toast-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  opacity: 0.7;
  color: inherit;
  padding: 0;
  line-height: 1;
  
  &:hover {
    opacity: 1;
  }
}

// Animations
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
```

**File: `app/frontend/src/composables/useWebSocket.ts` (UPDATE)**

```typescript
// Add to existing useWebSocket.ts

import { useToast } from './useToast'

export function useWebSocket() {
  const { showErrorToast } = useToast()
  
  // ... existing code ...
  
  // NEW: Handle recording failure messages
  subscribe('recording_failed', (data: any) => {
    const { recording_id, streamer_name, error_message, timestamp } = data
    
    console.error(`🚨 Recording failed for ${streamer_name}:`, error_message)
    
    // Show error toast to user (10 second duration for critical errors)
    showErrorToast(
      `Recording Failed: ${streamer_name}`,
      error_message || 'Unknown error occurred during recording',
      { duration: 10000 }
    )
  })
  
  return {
    // ... existing exports ...
  }
}
```

**File: `app/frontend/src/App.vue` (UPDATE)**

```vue
<template>
  <div id="app">
    <Navbar />
    <main>
      <RouterView />
    </main>
    
    <!-- NEW: Toast notifications -->
    <ToastContainer />
  </div>
</template>

<script setup lang="ts">
import ToastContainer from '@/components/ToastContainer.vue'
// ... existing imports ...
</script>
```

### B. Settings UI Feedback Implementation

**File: `app/frontend/src/composables/useRecordingSettings.ts` (UPDATE)**

```typescript
import { useToast } from './useToast'

export function useRecordingSettings() {
  const { showSuccessToast, showErrorToast } = useToast()
  
  // ... existing code ...
  
  async function saveSettings() {
    isSaving.value = true
    
    try {
      const response = await fetch('/api/recording/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings.value)
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Server returned ${response.status}`)
      }
      
      // ✅ SUCCESS FEEDBACK
      showSuccessToast(
        'Settings Saved',
        'Recording settings updated successfully'
      )
      
    } catch (error) {
      // ❌ ERROR FEEDBACK
      showErrorToast(
        'Failed to Save Settings',
        error instanceof Error ? error.message : 'An unknown error occurred'
      )
      
      console.error('Failed to save settings:', error)
    } finally {
      isSaving.value = false
    }
  }
  
  return {
    // ... existing exports ...
    saveSettings
  }
}
```

**Apply same pattern to:**
- `useProxySettings.ts` - For proxy add/remove/test operations
- `useNotificationSettings.ts` - For notification config saves
- `useCodecSettings.ts` - For codec preference saves

**Button Component with Loading State:**

```vue
<template>
  <div class="form-actions">
    <button
      @click="handleSave"
      :disabled="isSaving"
      class="btn btn-primary"
      :class="{ 'btn-loading': isSaving }"
    >
      <span v-if="isSaving" class="spinner"></span>
      {{ isSaving ? 'Saving...' : 'Save Settings' }}
    </button>
  </div>
</template>

<style scoped lang="scss">
.btn-loading {
  position: relative;
  pointer-events: none;
  
  .spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-right: 8px;
    vertical-align: middle;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
```

---

## 🎯 **Summary (Updated: Nov 12, 2025)**

### ✅ Implemented Features (Needs Testing)

#### Backend Complete:
1. ✅ **H.265/AV1 Codec Support** (Commits: b219ad1e, c415ec28, da591a46, 7aba76ce, 820032de)
   - Migration 024 applied
   - Streamlink 8.0.0 --twitch-supported-codecs integration
   - UI in RecordingSettingsPanel.vue

2. ✅ **Stream Recovery After Restart** (Commit: 82432f47)
   - Smart zombie cleanup with Twitch API check
   - Resume recording if streamer still live
   - Prevents data loss on app restarts

3. ✅ **Video Player Routing Fix** (Commit: 1752760a)
   - Fixed navigation to /streamer/:streamerId/stream/:streamId/watch
   - VideoCard and VideosView corrected

4. ✅ **Apprise Recording Events - Backend** (Partially Complete)
   - Migration 027: Error tracking (error_message, failure_reason, failure_timestamp)
   - Migration 028: Notification settings (notify_recording_started, notify_recording_failed, notify_recording_completed)
   - ⏸️ **Missing**: Frontend UI + process_manager.py integration

### 📝 Not Implemented (Planned)

1. 📝 **Recording Failure Detection & Propagation** - CRITICAL
   - Frontend shows "Recording" but Streamlink fails silently
   - Needs WebSocket error events + Toast notifications

2. 📝 **Toast Notification System** - HIGH
   - Required for Recording Failure Detection
   - Required for Settings UI feedback

3. 📝 **Multi-Proxy System with Health Checks** - CRITICAL
   - Current proxy DOWN, all recordings fail
   - Automatic failover needed

4. 📝 **Streamlink Recovery on Proxy Failure** - HIGH
   - Depends on Multi-Proxy system
   - Uses existing segment merge logic

5. 📝 **Settings UI Feedback Improvements** - MEDIUM
   - Better save confirmations
   - Depends on Toast system

### 🗄️ Database Migrations Status

- ✅ Migration 024: Codec preferences (applied)
- ✅ Migration 027: Error tracking (applied)
- ✅ Migration 028: System notification settings (applied)
- 📝 Migration 025: Proxy settings (NOT CREATED)
- 📝 Migration 026: Recovery tracking (NOT CREATED)

### 🧪 Testing Required (High Priority)

1. **H.265/AV1 Testing**:
   - [ ] Test with h264-only channel
   - [ ] Test with h265-capable channel (1440p)
   - [ ] Verify fallback behavior
   - [ ] Check file sizes (h265 ~30% smaller)
   - [ ] Test playback compatibility

2. **Stream Recovery Testing**:
   - [ ] Start recording → restart app while live → verify resume
   - [ ] Start recording → restart app after offline → verify stopped

3. **Video Player Testing**:
   - [ ] Click video card → verify player loads
   - [ ] Click play button → verify player loads
   - [ ] Test video playback controls

4. **Apprise Notification Testing** (Backend Only):
   - [ ] Verify Migration 027 columns exist (error_message, failure_reason, failure_timestamp)
   - [ ] Verify Migration 028 columns exist (notify_recording_started/failed/completed)
   - [ ] Check default values: started=false, failed=true, completed=false

### 📊 Implementation Progress

**Completed**: 4/8 major features (50%)  
**Testing Status**: 0/4 tested  
**Next Priority**: Testing → Recording Failure Detection → Multi-Proxy System

