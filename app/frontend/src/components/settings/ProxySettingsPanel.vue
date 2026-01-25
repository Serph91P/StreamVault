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
    <div v-else class="proxy-content">
      <!-- System Status Section -->
      <section class="settings-section">
        <div class="section-header">
          <h3 class="section-title">
            <span class="status-icon-wrapper">
              <svg v-if="proxySystemStatus.status === 'healthy'" class="status-svg status-healthy"><use href="#icon-check-circle" /></svg>
              <svg v-else-if="proxySystemStatus.status === 'degraded'" class="status-svg status-warning"><use href="#icon-alert-triangle" /></svg>
              <svg v-else-if="proxySystemStatus.status === 'critical'" class="status-svg status-danger"><use href="#icon-x-circle" /></svg>
              <svg v-else-if="proxySystemStatus.status === 'fallback'" class="status-svg status-info"><use href="#icon-refresh-cw" /></svg>
              <svg v-else-if="proxySystemStatus.status === 'disabled'" class="status-svg status-muted"><use href="#icon-pause-circle" /></svg>
              <svg v-else class="status-svg status-muted"><use href="#icon-help-circle" /></svg>
            </span>
            Proxy System Status
          </h3>
          <p class="section-description">{{ proxySystemStatus.message }}</p>
        </div>

        <!-- Statistics Grid -->
        <div class="stats-grid">
          <div class="stat-card">
            <span class="stat-value">{{ enabledProxyCount }}</span>
            <span class="stat-label">Enabled</span>
          </div>
          <div class="stat-card stat-healthy">
            <span class="stat-value">{{ healthyProxyCount }}</span>
            <span class="stat-label">Healthy</span>
          </div>
          <div class="stat-card stat-degraded">
            <span class="stat-value">{{ degradedProxyCount }}</span>
            <span class="stat-label">Degraded</span>
          </div>
          <div class="stat-card stat-failed">
            <span class="stat-value">{{ failedProxyCount }}</span>
            <span class="stat-label">Failed</span>
          </div>
        </div>
      </section>

      <!-- Proxy Servers Section -->
      <section class="settings-section">
        <div class="section-header">
          <h3 class="section-title">Proxy Servers</h3>
          <button @click="showAddDialog = true" class="btn btn-primary btn-sm">
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

        <!-- Proxy List -->
        <div v-else class="proxy-list">
          <div
            v-for="proxy in sortedProxies"
            :key="proxy.id"
            class="proxy-card"
            :class="[
              `proxy-status-${proxy.health_status}`,
              { 'proxy-disabled': !proxy.enabled }
            ]"
          >
            <!-- Proxy Header Row -->
            <div class="proxy-header-row">
              <div class="proxy-main-info">
                <code class="proxy-url">{{ proxy.masked_url }}</code>
                <div class="proxy-badges">
                  <span class="health-badge" :class="`health-${proxy.health_status}`">
                    <svg class="health-icon"><use :href="`#icon-${proxy.health_status === 'healthy' ? 'check-circle' : proxy.health_status === 'degraded' ? 'alert-triangle' : proxy.health_status === 'failed' ? 'x-circle' : 'help-circle'}`" /></svg>
                    {{ proxy.health_status }}
                  </span>
                  <span class="priority-badge">Priority: {{ proxy.priority }}</span>
                </div>
              </div>
              <label class="toggle-switch">
                <input
                  type="checkbox"
                  :checked="proxy.enabled"
                  @change="handleToggleProxy(proxy.id, !proxy.enabled)"
                />
                <span class="toggle-slider"></span>
              </label>
            </div>

            <!-- Proxy Stats Grid -->
            <div class="proxy-stats-grid">
              <div class="proxy-stat">
                <span class="proxy-stat-label">Response Time</span>
                <span class="proxy-stat-value">
                  {{ proxy.response_time_ms !== null ? `${proxy.response_time_ms}ms` : 'N/A' }}
                </span>
              </div>
              <div class="proxy-stat">
                <span class="proxy-stat-label">Success Rate</span>
                <span class="proxy-stat-value">{{ getSuccessRate(proxy) }}</span>
              </div>
              <div class="proxy-stat">
                <span class="proxy-stat-label">Failures</span>
                <span class="proxy-stat-value">{{ proxy.consecutive_failures }}</span>
              </div>
              <div class="proxy-stat">
                <span class="proxy-stat-label">Last Check</span>
                <span class="proxy-stat-value">{{ formatLastCheck(proxy.last_check) }}</span>
              </div>
            </div>

            <!-- Error Message (if any) -->
            <div v-if="proxy.last_error" class="proxy-error-message">
              <strong>Last Error:</strong> {{ proxy.last_error }}
            </div>

            <!-- Action Buttons -->
            <div class="proxy-action-buttons">
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
      </section>

      <!-- System Configuration Section -->
      <section class="settings-section">
        <div class="section-header">
          <h3 class="section-title">System Configuration</h3>
          <button @click="handleSaveConfig" class="btn btn-primary btn-sm" :disabled="isSavingConfig">
            <svg class="icon">
              <use href="#icon-check" />
            </svg>
            {{ isSavingConfig ? 'Saving...' : 'Save Config' }}
          </button>
        </div>

        <div class="config-options">
          <!-- Enable Proxy System -->
          <div class="config-option">
            <label class="checkbox-label">
              <input type="checkbox" v-model="localConfig.enable_proxy" />
              <span class="checkbox-text">Enable Proxy System</span>
            </label>
            <p class="config-help">
              When enabled, recordings will use configured proxies for connections
            </p>
          </div>

          <!-- Health Check Enabled -->
          <div class="config-option">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="localConfig.proxy_health_check_enabled"
                :disabled="!localConfig.enable_proxy"
              />
              <span class="checkbox-text">Enable Automatic Health Checks</span>
            </label>
            <p class="config-help">
              Automatically test proxy health at regular intervals
            </p>
          </div>

          <!-- Health Check Interval -->
          <div class="config-option config-option-input">
            <label class="config-label">Health Check Interval (seconds)</label>
            <input
              type="number"
              v-model.number="localConfig.proxy_health_check_interval_seconds"
              class="form-control"
              min="60"
              max="3600"
              step="60"
              :disabled="!localConfig.proxy_health_check_enabled"
            />
            <p class="config-help">
              How often to check proxy health (minimum 60 seconds)
            </p>
          </div>

          <!-- Max Consecutive Failures -->
          <div class="config-option config-option-input">
            <label class="config-label">Max Consecutive Failures</label>
            <input
              type="number"
              v-model.number="localConfig.proxy_max_consecutive_failures"
              class="form-control"
              min="1"
              max="10"
              :disabled="!localConfig.enable_proxy"
            />
            <p class="config-help">
              Auto-disable proxy after this many consecutive failures
            </p>
          </div>

          <!-- Fallback to Direct Connection -->
          <div class="config-option">
            <label class="checkbox-label">
              <input
                type="checkbox"
                v-model="localConfig.fallback_to_direct_connection"
                :disabled="!localConfig.enable_proxy"
              />
              <span class="checkbox-text">Fallback to Direct Connection</span>
            </label>
            <p class="config-help">
              When all proxies fail, attempt direct connection without proxy
            </p>
          </div>
        </div>
      </section>
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
  // Icons handled via CSS, return empty
  return ''
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
// PROXY SETTINGS PANEL - Clean, Organized Layout
// ============================================================================

.proxy-settings-panel {
  max-width: 100%;
}

.proxy-content {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-8;
}

// ============================================================================
// SETTINGS SECTIONS
// ============================================================================

.settings-section {
  padding-bottom: v.$spacing-6;
  border-bottom: 1px solid var(--border-color);
  
  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: v.$spacing-4;
  margin-bottom: v.$spacing-5;
  
  @include m.respond-below('sm') {
    flex-direction: column;
    align-items: stretch;
    gap: v.$spacing-3;
  }
}

.section-title {
  font-size: v.$text-lg;
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: v.$spacing-2;
}

.section-description {
  font-size: v.$text-sm;
  color: var(--text-secondary);
  margin: v.$spacing-1 0 0 0;
}

.status-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-svg {
  width: 20px;
  height: 20px;
  
  &.status-healthy { color: var(--success-color); }
  &.status-warning { color: var(--warning-color); }
  &.status-danger { color: var(--danger-color); }
  &.status-info { color: var(--primary-color); }
  &.status-muted { color: var(--text-muted); }
}

// ============================================================================
// STATS GRID
// ============================================================================

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: v.$spacing-4;
  
  @include m.respond-below('md') {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr 1fr;
    gap: v.$spacing-3;
  }
}

.stat-card {
  padding: v.$spacing-4;
  background: var(--background-hover);
  border-radius: var(--radius-md);
  text-align: center;
  border: 1px solid var(--border-color);
  
  .stat-value {
    display: block;
    font-size: v.$text-2xl;
    font-weight: v.$font-bold;
    color: var(--text-primary);
    margin-bottom: v.$spacing-1;
  }
  
  .stat-label {
    display: block;
    font-size: v.$text-sm;
    color: var(--text-secondary);
  }
  
  &.stat-healthy .stat-value {
    color: var(--success-color);
  }
  
  &.stat-degraded .stat-value {
    color: var(--warning-color);
  }
  
  &.stat-failed .stat-value {
    color: var(--danger-color);
  }
}

// ============================================================================
// PROXY LIST
// ============================================================================

.proxy-list {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-4;
}

.proxy-card {
  padding: v.$spacing-5;
  background: var(--background-hover);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  transition: all v.$duration-200 v.$ease-out;
  
  &:hover {
    border-color: var(--primary-color);
  }
  
  &.proxy-disabled {
    opacity: 0.6;
  }
  
  &.proxy-status-healthy {
    background: linear-gradient(135deg, rgba(var(--success-500-rgb), 0.1) 0%, transparent 50%);
    border-color: var(--success-color);
  }
  
  &.proxy-status-degraded {
    background: linear-gradient(135deg, rgba(var(--warning-500-rgb), 0.1) 0%, transparent 50%);
    border-color: var(--warning-color);
  }
  
  &.proxy-status-failed {
    background: linear-gradient(135deg, rgba(var(--danger-500-rgb), 0.1) 0%, transparent 50%);
    border-color: var(--danger-color);
  }
}

// Proxy Header Row
.proxy-header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: v.$spacing-4;
  margin-bottom: v.$spacing-4;
  
  @include m.respond-below('sm') {
    flex-direction: column;
    gap: v.$spacing-3;
  }
}

.proxy-main-info {
  flex: 1;
  min-width: 0;
}

.proxy-url {
  font-family: var(--font-mono);
  font-size: v.$text-sm;
  color: var(--primary-color);
  background: var(--background-darker);
  padding: v.$spacing-2 v.$spacing-3;
  border-radius: var(--radius-sm);
  display: inline-block;
  word-break: break-all;
  margin-bottom: v.$spacing-2;
}

.proxy-badges {
  display: flex;
  flex-wrap: wrap;
  gap: v.$spacing-2;
  align-items: center;
}

.health-badge {
  display: inline-flex;
  align-items: center;
  gap: v.$spacing-1;
  padding: v.$spacing-1 v.$spacing-2;
  border-radius: var(--radius-pill);
  font-size: v.$text-xs;
  font-weight: v.$font-semibold;
  text-transform: capitalize;
  
  .health-icon {
    width: 14px;
    height: 14px;
    flex-shrink: 0;
  }
  
  &.health-healthy {
    background: rgba(46, 213, 115, 0.15);
    color: var(--success-color);
    border: 1px solid rgba(46, 213, 115, 0.3);
    
    .health-icon { stroke: var(--success-color); fill: none; }
  }
  
  &.health-degraded {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning-color);
    border: 1px solid rgba(245, 158, 11, 0.3);
    
    .health-icon { stroke: var(--warning-color); fill: none; }
  }
  
  &.health-failed {
    background: rgba(239, 68, 68, 0.15);
    color: var(--danger-color);
    border: 1px solid rgba(239, 68, 68, 0.3);
    
    .health-icon { stroke: var(--danger-color); fill: none; }
  }
  
  &.health-unknown {
    background: rgba(148, 163, 184, 0.15);
    color: var(--text-secondary);
    border: 1px solid rgba(148, 163, 184, 0.3);
    
    .health-icon { stroke: var(--text-secondary); fill: none; }
  }
}

.priority-badge {
  font-size: v.$text-xs;
  color: var(--text-secondary);
  padding: v.$spacing-1 v.$spacing-2;
  background: var(--background-darker);
  border-radius: var(--radius-sm);
}

// Toggle Switch
.toggle-switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 26px;
  flex-shrink: 0;
  
  input {
    opacity: 0;
    width: 0;
    height: 0;
  }
  
  .toggle-slider {
    position: absolute;
    cursor: pointer;
    inset: 0;
    background-color: var(--background-darker);
    border: 1px solid var(--border-color);
    border-radius: 26px;
    transition: v.$transition-all;
    
    &::before {
      position: absolute;
      content: "";
      height: 20px;
      width: 20px;
      left: 2px;
      bottom: 2px;
      background-color: var(--text-secondary);
      border-radius: 50%;
      transition: v.$transition-all;
    }
  }
  
  input:checked + .toggle-slider {
    background-color: var(--primary-color);
    border-color: var(--primary-color);
    
    &::before {
      transform: translateX(22px);
      background-color: white;
    }
  }
}

// Proxy Stats Grid
.proxy-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: v.$spacing-3;
  padding: v.$spacing-4;
  background: var(--background-darker);
  border-radius: var(--radius-md);
  margin-bottom: v.$spacing-4;
  
  @include m.respond-below('md') {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr 1fr;
  }
}

.proxy-stat {
  text-align: center;
  
  .proxy-stat-label {
    display: block;
    font-size: v.$text-xs;
    color: var(--text-secondary);
    margin-bottom: v.$spacing-1;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .proxy-stat-value {
    display: block;
    font-size: v.$text-base;
    font-weight: v.$font-semibold;
    color: var(--text-primary);
  }
}

// Proxy Error Message
.proxy-error-message {
  padding: v.$spacing-3;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-sm);
  color: var(--danger-color);
  font-size: v.$text-sm;
  margin-bottom: v.$spacing-4;
  
  strong {
    color: var(--danger-color);
  }
}

// Proxy Action Buttons
.proxy-action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: v.$spacing-3;
  padding-top: v.$spacing-4;
  border-top: 1px solid var(--border-color);
  
  @include m.respond-below('sm') {
    .btn {
      flex: 1;
      min-width: calc(50% - v.$spacing-2);
    }
  }
}

// ============================================================================
// CONFIGURATION OPTIONS
// ============================================================================

.config-options {
  display: flex;
  flex-direction: column;
  gap: v.$spacing-5;
}

.config-option {
  padding-bottom: v.$spacing-4;
  border-bottom: 1px solid rgba(var(--border-color-rgb), 0.3);
  
  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
}

.config-option-input {
  .form-control {
    max-width: 200px;
    margin-top: v.$spacing-2;
  }
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  cursor: pointer;
  
  input[type="checkbox"] {
    width: 18px;
    height: 18px;
    accent-color: var(--primary-color);
    cursor: pointer;
  }
  
  .checkbox-text {
    font-weight: v.$font-medium;
    color: var(--text-primary);
  }
}

.config-label {
  display: block;
  font-weight: v.$font-medium;
  color: var(--text-primary);
  margin-bottom: v.$spacing-1;
}

.config-help {
  font-size: v.$text-sm;
  color: var(--text-secondary);
  margin: v.$spacing-2 0 0 0;
  line-height: 1.5;
}

// ============================================================================
// MODAL STYLES
// ============================================================================

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: v.$spacing-4;
}

.modal-card {
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: v.$spacing-5;
  
  h3 {
    margin: 0;
    font-size: v.$text-xl;
    font-weight: v.$font-semibold;
    color: var(--text-primary);
  }
}

.btn-close {
  background: none;
  border: none;
  font-size: v.$text-2xl;
  color: var(--text-secondary);
  cursor: pointer;
  padding: v.$spacing-1;
  line-height: 1;
  
  &:hover {
    color: var(--text-primary);
  }
}

.modal-body {
  .form-group {
    margin-bottom: v.$spacing-4;
  }
  
  .form-label {
    display: block;
    font-weight: v.$font-medium;
    color: var(--text-primary);
    margin-bottom: v.$spacing-2;
  }
  
  .form-control {
    width: 100%;
  }
  
  .help-text {
    font-size: v.$text-sm;
    color: var(--text-secondary);
    margin-top: v.$spacing-1;
  }
  
  .error-text {
    font-size: v.$text-sm;
    color: var(--danger-color);
    margin-top: v.$spacing-1;
  }
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: v.$spacing-3;
  margin-top: v.$spacing-5;
  padding-top: v.$spacing-4;
  border-top: 1px solid var(--border-color);
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .proxy-action-buttons {
    justify-content: stretch;
    
    .btn {
      flex: 1;
    }
  }
}
</style>
