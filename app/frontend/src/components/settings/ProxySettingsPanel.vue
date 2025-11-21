<template>
  <div class="proxy-settings-panel">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <LoadingSkeleton type="card" />
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="alert alert-danger">
      <strong>Error:</strong> {{ error }}
      <button @click="fetchProxies" class="btn btn-sm btn-secondary" style="margin-left: 12px;">
        Retry
      </button>
    </div>

    <!-- Main Content -->
    <div v-else>
      <!-- System Status Card -->
      <GlassCard class="status-card" :class="`status-${proxySystemStatus.status}`">
        <div class="status-header">
          <div class="status-icon">
            <span v-if="proxySystemStatus.status === 'healthy'">✅</span>
            <span v-else-if="proxySystemStatus.status === 'degraded'">⚠️</span>
            <span v-else-if="proxySystemStatus.status === 'critical'">❌</span>
            <span v-else-if="proxySystemStatus.status === 'fallback'">🔄</span>
            <span v-else-if="proxySystemStatus.status === 'disabled'">⏸️</span>
            <span v-else>❓</span>
          </div>
          <div class="status-content">
            <h3 class="status-title">Proxy System Status</h3>
            <p class="status-message">{{ proxySystemStatus.message }}</p>
          </div>
        </div>

        <!-- Statistics -->
        <div class="status-stats">
          <div class="stat-item">
            <span class="stat-label">Enabled</span>
            <span class="stat-value">{{ enabledProxyCount }}</span>
          </div>
          <div class="stat-item stat-healthy">
            <span class="stat-label">Healthy</span>
            <span class="stat-value">{{ healthyProxyCount }}</span>
          </div>
          <div class="stat-item stat-degraded">
            <span class="stat-label">Degraded</span>
            <span class="stat-value">{{ degradedProxyCount }}</span>
          </div>
          <div class="stat-item stat-failed">
            <span class="stat-label">Failed</span>
            <span class="stat-value">{{ failedProxyCount }}</span>
          </div>
        </div>
      </GlassCard>

      <!-- Proxy List -->
      <GlassCard class="proxy-list-card">
        <div class="card-header">
          <h3>Proxy Servers</h3>
          <button @click="showAddDialog = true" class="btn btn-primary">
            <svg class="icon">
              <use href="#icon-plus" />
            </svg>
            Add Proxy
          </button>
        </div>

        <!-- Empty State -->
        <EmptyState
          v-if="proxies.length === 0"
          icon="icon-server"
          title="No Proxies Configured"
          description="Add proxy servers to improve connection reliability and enable failover"
          action-text="Add First Proxy"
          @action="showAddDialog = true"
        />

        <!-- Proxy Cards -->
        <div v-else class="proxy-grid">
          <div
            v-for="proxy in sortedProxies"
            :key="proxy.id"
            class="proxy-card"
            :class="`proxy-status-${proxy.health_status}`"
          >
            <!-- Proxy Header -->
            <div class="proxy-header">
              <div class="proxy-info">
                <div class="proxy-url">{{ proxy.masked_url }}</div>
                <div class="proxy-meta">
                  <span class="badge badge-sm" :class="`badge-${getHealthBadgeClass(proxy.health_status)}`">
                    {{ getHealthIcon(proxy.health_status) }} {{ proxy.health_status }}
                  </span>
                  <span class="proxy-priority">Priority: {{ proxy.priority }}</span>
                </div>
              </div>

              <!-- Toggle -->
              <div class="proxy-toggle">
                <label class="switch">
                  <input
                    type="checkbox"
                    :checked="proxy.enabled"
                    @change="handleToggleProxy(proxy.id, !proxy.enabled)"
                  />
                  <span class="slider"></span>
                </label>
              </div>
            </div>

            <!-- Proxy Stats -->
            <div class="proxy-stats">
              <div class="stat">
                <span class="stat-label">Response Time</span>
                <span class="stat-value">
                  {{ proxy.response_time_ms !== null ? `${proxy.response_time_ms}ms` : 'N/A' }}
                </span>
              </div>
              <div class="stat">
                <span class="stat-label">Success Rate</span>
                <span class="stat-value">
                  {{ getSuccessRate(proxy) }}
                </span>
              </div>
              <div class="stat">
                <span class="stat-label">Failures</span>
                <span class="stat-value">{{ proxy.consecutive_failures }}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Last Check</span>
                <span class="stat-value">{{ formatLastCheck(proxy.last_check) }}</span>
              </div>
            </div>

            <!-- Error Message -->
            <div v-if="proxy.last_error" class="proxy-error">
              <strong>Last Error:</strong> {{ proxy.last_error }}
            </div>

            <!-- Actions -->
            <div class="proxy-actions">
              <button
                @click="handleTestProxy(proxy.id)"
                class="btn btn-sm btn-secondary"
                :disabled="testingProxyId === proxy.id"
              >
                <svg class="icon">
                  <use href="#icon-refresh" />
                </svg>
                {{ testingProxyId === proxy.id ? 'Testing...' : 'Test Now' }}
              </button>

              <button
                @click="showPriorityDialog(proxy)"
                class="btn btn-sm btn-secondary"
              >
                Priority
              </button>

              <button
                @click="handleDeleteProxy(proxy)"
                class="btn btn-sm btn-danger"
              >
                <svg class="icon">
                  <use href="#icon-trash" />
                </svg>
                Delete
              </button>
            </div>
          </div>
        </div>
      </GlassCard>

      <!-- System Configuration -->
      <GlassCard class="config-card">
        <div class="card-header">
          <h3>System Configuration</h3>
          <button @click="handleSaveConfig" class="btn btn-primary" :disabled="isSavingConfig">
            <svg class="icon">
              <use href="#icon-check" />
            </svg>
            {{ isSavingConfig ? 'Saving...' : 'Save Config' }}
          </button>
        </div>

        <div class="config-form">
          <!-- Enable Proxy System -->
          <div class="form-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="localConfig.enable_proxy" />
              <span>Enable Proxy System</span>
            </label>
            <p class="help-text">
              When enabled, recordings will use configured proxies for connections
            </p>
          </div>

          <!-- Health Check Enabled -->
          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="localConfig.proxy_health_check_enabled"
                :disabled="!localConfig.enable_proxy"
              />
              <span>Enable Automatic Health Checks</span>
            </label>
            <p class="help-text">
              Automatically test proxy health at regular intervals
            </p>
          </div>

          <!-- Health Check Interval -->
          <div class="form-group">
            <label class="form-label">Health Check Interval (seconds)</label>
            <input
              type="number"
              v-model.number="localConfig.proxy_health_check_interval_seconds"
              class="form-control"
              min="60"
              max="3600"
              step="60"
              :disabled="!localConfig.proxy_health_check_enabled"
            />
            <p class="help-text">
              How often to check proxy health (minimum 60 seconds)
            </p>
          </div>

          <!-- Max Consecutive Failures -->
          <div class="form-group">
            <label class="form-label">Max Consecutive Failures</label>
            <input
              type="number"
              v-model.number="localConfig.proxy_max_consecutive_failures"
              class="form-control"
              min="1"
              max="10"
              :disabled="!localConfig.enable_proxy"
            />
            <p class="help-text">
              Auto-disable proxy after this many consecutive failures
            </p>
          </div>

          <!-- Fallback to Direct Connection -->
          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="localConfig.fallback_to_direct_connection"
                :disabled="!localConfig.enable_proxy"
              />
              <span>Fallback to Direct Connection</span>
            </label>
            <p class="help-text">
              When all proxies fail, attempt direct connection without proxy
            </p>
          </div>
        </div>
      </GlassCard>
    </div>

    <!-- Add Proxy Dialog -->
    <Teleport to="body">
      <div v-if="showAddDialog" class="modal-overlay" @click.self="closeAddDialog">
        <GlassCard class="modal-card">
          <div class="modal-header">
            <h3>Add Proxy Server</h3>
            <button @click="closeAddDialog" class="btn-close">×</button>
          </div>

          <div class="modal-body">
            <form @submit.prevent="handleAddProxy">
              <!-- Proxy URL -->
              <div class="form-group">
                <label class="form-label">Proxy URL *</label>
                <input
                  v-model="newProxy.proxy_url"
                  type="text"
                  class="form-control"
                  :class="{ error: proxyUrlError }"
                  placeholder="http://user:pass@host:port"
                  required
                />
                <p v-if="proxyUrlError" class="error-text">{{ proxyUrlError }}</p>
                <p v-else class="help-text">
                  Format: http://[user:pass@]host:port or socks5://[user:pass@]host:port
                </p>
              </div>

              <!-- Priority -->
              <div class="form-group">
                <label class="form-label">Priority</label>
                <input
                  v-model.number="newProxy.priority"
                  type="number"
                  class="form-control"
                  min="1"
                  max="100"
                />
                <p class="help-text">
                  Lower numbers = higher priority (1 = highest priority)
                </p>
              </div>

              <!-- Enabled -->
              <div class="form-group">
                <label class="checkbox-label">
                  <input type="checkbox" v-model="newProxy.enabled" />
                  <span>Enable immediately</span>
                </label>
              </div>

              <!-- Examples -->
              <div class="proxy-examples">
                <h4>Examples:</h4>
                <ul>
                  <li><code>http://proxy.example.com:8080</code> - Simple HTTP proxy</li>
                  <li><code>http://user:pass@proxy.example.com:8080</code> - With authentication</li>
                  <li><code>socks5://user:pass@proxy.example.com:1080</code> - SOCKS5 proxy</li>
                </ul>
              </div>

              <!-- Actions -->
              <div class="modal-actions">
                <button type="button" @click="closeAddDialog" class="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" class="btn btn-primary" :disabled="isAddingProxy || !!proxyUrlError">
                  {{ isAddingProxy ? 'Adding...' : 'Add Proxy' }}
                </button>
              </div>
            </form>
          </div>
        </GlassCard>
      </div>
    </Teleport>

    <!-- Update Priority Dialog -->
    <Teleport to="body">
      <div v-if="showPriorityDialogVisible" class="modal-overlay" @click.self="closePriorityDialog">
        <GlassCard class="modal-card modal-sm">
          <div class="modal-header">
            <h3>Update Priority</h3>
            <button @click="closePriorityDialog" class="btn-close">×</button>
          </div>

          <div class="modal-body">
            <form @submit.prevent="handleUpdatePriority">
              <div class="form-group">
                <label class="form-label">Priority for {{ selectedProxy?.masked_url }}</label>
                <input
                  v-model.number="newPriority"
                  type="number"
                  class="form-control"
                  min="1"
                  max="100"
                  required
                />
                <p class="help-text">
                  Lower numbers = higher priority (1 = highest)
                </p>
              </div>

              <div class="modal-actions">
                <button type="button" @click="closePriorityDialog" class="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" class="btn btn-primary" :disabled="isUpdatingPriority">
                  {{ isUpdatingPriority ? 'Updating...' : 'Update' }}
                </button>
              </div>
            </form>
          </div>
        </GlassCard>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useProxySettings } from '@/composables/useProxySettings'
import { useToast } from '@/composables/useToast'
import type { ProxySettings, ProxyAddRequest } from '@/types/proxy'
import GlassCard from '@/components/cards/GlassCard.vue'
import LoadingSkeleton from '@/components/LoadingSkeleton.vue'
import EmptyState from '@/components/EmptyState.vue'

// Composables
const {
  proxies,
  config,
  isLoading,
  error,
  healthyProxyCount,
  degradedProxyCount,
  failedProxyCount,
  enabledProxyCount,
  proxySystemStatus,
  fetchProxies,
  addProxy,
  deleteProxy,
  toggleProxy,
  testProxy,
  updatePriority,
  updateConfig
} = useProxySettings()

const toast = useToast()

// Local state
const showAddDialog = ref(false)
const showPriorityDialogVisible = ref(false)
const selectedProxy = ref<ProxySettings | null>(null)
const newPriority = ref(1)
const testingProxyId = ref<number | null>(null)
const isAddingProxy = ref(false)
const isUpdatingPriority = ref(false)
const isSavingConfig = ref(false)

// Local config (editable copy)
const localConfig = ref({ ...config.value })

// Watch config changes
watch(config, (newConfig) => {
  localConfig.value = { ...newConfig }
}, { deep: true })

// New proxy form
const newProxy = ref<ProxyAddRequest>({
  proxy_url: '',
  priority: 10,
  enabled: true
})

// Computed
const sortedProxies = computed(() => {
  return [...proxies.value].sort((a, b) => a.priority - b.priority)
})

const proxyUrlError = computed(() => {
  const url = newProxy.value.proxy_url.trim()
  if (!url) return ''

  // Check format: protocol://[user:pass@]host:port
  // Allow optional auth: username:password@
  // Then require host:port at the end
  if (!url.match(/^(http|https|socks5):\/\/(.+@)?[^:]+:\d+$/)) {
    return 'Invalid format. Use: protocol://[user:pass@]host:port'
  }

  return ''
})

// Helper methods
function getHealthIcon(status: string): string {
  switch (status) {
    case 'healthy': return '✅'
    case 'degraded': return '⚠️'
    case 'failed': return '❌'
    default: return '❓'
  }
}

function getHealthBadgeClass(status: string): string {
  switch (status) {
    case 'healthy': return 'success'
    case 'degraded': return 'warning'
    case 'failed': return 'danger'
    default: return 'secondary'
  }
}

function getSuccessRate(proxy: ProxySettings): string {
  if (proxy.total_requests === 0) return 'N/A'
  const rate = (proxy.successful_requests / proxy.total_requests) * 100
  return `${rate.toFixed(1)}%`
}

function formatLastCheck(lastCheck: string | null): string {
  if (!lastCheck) return 'Never'

  const date = new Date(lastCheck)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins === 1) return '1 minute ago'
  if (diffMins < 60) return `${diffMins} minutes ago`

  const diffHours = Math.floor(diffMins / 60)
  if (diffHours === 1) return '1 hour ago'
  if (diffHours < 24) return `${diffHours} hours ago`

  return date.toLocaleString()
}

// Action handlers
async function handleAddProxy() {
  if (proxyUrlError.value) return

  isAddingProxy.value = true

  try {
    await addProxy(newProxy.value)
    toast.success(`Proxy added successfully! Testing health...`)
    closeAddDialog()
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to add proxy'
    toast.error(errorMsg)
  } finally {
    isAddingProxy.value = false
  }
}

function closeAddDialog() {
  showAddDialog.value = false
  newProxy.value = {
    proxy_url: '',
    priority: 10,
    enabled: true
  }
}

async function handleDeleteProxy(proxy: ProxySettings) {
  try {
    const deleted = await deleteProxy(proxy.id, proxy.masked_url)
    if (deleted) {
      toast.success(`Proxy ${proxy.masked_url} deleted`)
    }
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to delete proxy'
    toast.error(errorMsg)
  }
}

async function handleToggleProxy(id: number, enabled: boolean) {
  try {
    await toggleProxy(id, enabled)
    toast.success(`Proxy ${enabled ? 'enabled' : 'disabled'}`)
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to toggle proxy'
    toast.error(errorMsg)
  }
}

async function handleTestProxy(id: number) {
  testingProxyId.value = id

  try {
    const result = await testProxy(id)
    const statusIcon = getHealthIcon(result.health_status)
    toast.success(
      `${statusIcon} Health check complete: ${result.health_status} ` +
      `(${result.response_time_ms ? result.response_time_ms + 'ms' : 'N/A'})`
    )
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to test proxy'
    toast.error(errorMsg)
  } finally {
    testingProxyId.value = null
  }
}

function showPriorityDialog(proxy: ProxySettings) {
  selectedProxy.value = proxy
  newPriority.value = proxy.priority
  showPriorityDialogVisible.value = true
}

function closePriorityDialog() {
  showPriorityDialogVisible.value = false
  selectedProxy.value = null
}

async function handleUpdatePriority() {
  if (!selectedProxy.value) return

  isUpdatingPriority.value = true

  try {
    await updatePriority(selectedProxy.value.id, newPriority.value)
    toast.success(`Priority updated to ${newPriority.value}`)
    closePriorityDialog()
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to update priority'
    toast.error(errorMsg)
  } finally {
    isUpdatingPriority.value = false
  }
}

async function handleSaveConfig() {
  isSavingConfig.value = true

  try {
    await updateConfig(localConfig.value)
    toast.success('Configuration saved successfully')
  } catch (e) {
    const errorMsg = e instanceof Error ? e.message : 'Failed to save configuration'
    toast.error(errorMsg)
  } finally {
    isSavingConfig.value = false
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// PROXY SETTINGS PANEL - Unified Design
// Most styles inherited from global _settings-panels.scss
// ============================================================================

// ============================================================================
// PROXY LIST
// ============================================================================

.proxy-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-3;
  margin-bottom: v.$spacing-6;
}

.proxy-item {
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  padding: v.$spacing-4;
  background: var(--background-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: v.$transition-all;
  
  &:hover {
    border-color: var(--primary-color);
    background: var(--background-hover);
  }
  
  &.active {
    border-color: var(--primary-color);
    background: var(--primary-bg);
  }
  
  &.unhealthy {
    border-color: var(--danger-color);
    opacity: 0.7;
  }
  
  @include m.respond-below('md') {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .proxy-status {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
    
    &.healthy {
      background: var(--success-color);
      box-shadow: 0 0 8px var(--success-color);
    }
    
    &.unhealthy {
      background: var(--danger-color);
      box-shadow: 0 0 8px var(--danger-color);
    }
    
    &.unknown {
      background: var(--text-secondary);
    }
  }
  
  .proxy-info {
    flex: 1;
    min-width: 0;
    
    .proxy-url {
      font-weight: v.$font-medium;
      color: var(--text-primary);
      word-break: break-all;
      margin-bottom: v.$spacing-1;
    }
    
    .proxy-meta {
      font-size: v.$text-sm;
      color: var(--text-secondary);
      display: flex;
      gap: v.$spacing-3;
      flex-wrap: wrap;
      
      .meta-item {
        display: flex;
        align-items: center;
        gap: v.$spacing-1;
        
        .meta-icon {
          font-size: v.$text-xs;
        }
      }
    }
  }
  
  .proxy-actions {
    display: flex;
    gap: v.$spacing-2;
    flex-shrink: 0;
    
    @include m.respond-below('md') {
      width: 100%;
      justify-content: space-between;
    }
  }
}

// ============================================================================
// ADD PROXY SECTION
// ============================================================================

.add-proxy-section {
  padding: v.$spacing-4;
  background: var(--background-hover);
  border-radius: var(--radius-md);
  margin-bottom: v.$spacing-6;
  
  .add-proxy-form {
    display: flex;
    gap: v.$spacing-3;
    align-items: flex-end;
    
    @include m.respond-below('md') {
      flex-direction: column;
      align-items: stretch;
    }
    
    .form-group {
      flex: 1;
    }
  }
}

// ============================================================================
// PROXY EXAMPLES
// ============================================================================

.proxy-examples {
  padding: v.$spacing-4;
  background: var(--info-bg-color);
  border: 1px solid var(--info-border-color);
  border-radius: var(--radius-md);
  
  .examples-title {
    font-weight: v.$font-semibold;
    color: var(--text-primary);
    margin-bottom: v.$spacing-3;
    display: flex;
    align-items: center;
    gap: v.$spacing-2;
  }
  
  .example-list {
    display: flex;
    flex-direction: column;
    gap: v.$spacing-2;
    
    .example-item {
      padding: v.$spacing-3;
      background: var(--background-card);
      border-radius: var(--radius-sm);
      
      .example-title {
        font-weight: v.$font-medium;
        color: var(--text-primary);
        margin-bottom: v.$spacing-1;
        font-size: v.$text-sm;
      }
      
      code {
        display: block;
        background: var(--background-darker);
        padding: v.$spacing-2;
        border-radius: var(--radius-sm);
        font-family: var(--font-mono);
        font-size: v.$text-xs;
        color: var(--primary-color);
        word-break: break-all;
      }
    }
  }
}

// ============================================================================
// PROXY TIPS
// ============================================================================

.proxy-tips {
  margin-top: v.$spacing-6;
  padding: v.$spacing-4;
  background: var(--warning-bg-color);
  border: 1px solid var(--warning-border-color);
  border-radius: var(--radius-md);
  
  .tips-title {
    font-weight: v.$font-semibold;
    color: var(--text-primary);
    margin-bottom: v.$spacing-3;
    display: flex;
    align-items: center;
    gap: v.$spacing-2;
  }
  
  .tips-list {
    list-style: none;
    padding: 0;
    
    li {
      position: relative;
      padding-left: v.$spacing-6;
      margin-bottom: v.$spacing-2;
      font-size: v.$text-sm;
      color: var(--text-secondary);
      line-height: 1.6;
      
      &:before {
        content: "•";
        position: absolute;
        left: v.$spacing-3;
        color: var(--warning-color);
        font-size: v.$text-lg;
        font-weight: v.$font-bold;
      }
    }
  }
}

// ============================================================================
// HEALTH CHECK SECTION
// ============================================================================

.health-check-section {
  margin-top: v.$spacing-6;
  
  .health-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: v.$spacing-3;
    margin-bottom: v.$spacing-4;
    
    .stat-card {
      padding: v.$spacing-3;
      background: var(--background-card);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      text-align: center;
      
      .stat-value {
        font-size: v.$text-2xl;
        font-weight: v.$font-bold;
        color: var(--text-primary);
        margin-bottom: v.$spacing-1;
      }
      
      .stat-label {
        font-size: v.$text-sm;
        color: var(--text-secondary);
      }
    }
  }
}

// ============================================================================
// EMPTY STATE
// ============================================================================

.empty-proxies {
  text-align: center;
  padding: v.$spacing-8 v.$spacing-4;
  
  .empty-icon {
    font-size: 4rem;
    color: var(--text-secondary);
    margin-bottom: v.$spacing-4;
    opacity: 0.5;
  }
  
  .empty-title {
    font-size: v.$text-xl;
    font-weight: v.$font-semibold;
    color: var(--text-primary);
    margin-bottom: v.$spacing-2;
  }
  
  .empty-description {
    color: var(--text-secondary);
    font-size: v.$text-base;
  }
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .form-actions {
    flex-direction: column;
    
    .btn {
      width: 100%;
    }
  }
  
  .proxy-actions {
    .btn {
      flex: 1;
    }
  }
}
</style>
