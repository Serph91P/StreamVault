<template>
  <div class="card-content">
      <!-- Connection Status -->
      <div class="connection-status">
        <div class="status-header">
          <div class="status-icon-wrapper" :class="statusClass">
            <svg class="status-icon" viewBox="0 0 24 24">
              <path fill="currentColor" d="M11.64 5.93H13.07V10.21H11.64M15.57 5.93H17V10.21H15.57M7 2L3.43 5.57V18.43H7.71V22L11.29 18.43H14.14L20.57 12V2M19.14 11.29L16.29 14.14H13.43L10.93 16.64V14.14H7.71V3.43H19.14Z"/>
            </svg>
          </div>
          <div class="status-info">
            <h3 class="status-title">{{ statusTitle }}</h3>
            <p class="status-description">{{ statusDescription }}</p>
          </div>
        </div>

        <div v-if="connectionStatus.connected" class="connection-details">
          <div class="detail-item">
            <span class="detail-label">Status:</span>
            <span class="detail-value" :class="{ 'text-success': connectionStatus.valid, 'text-warning': !connectionStatus.valid }">
              {{ connectionStatus.valid ? 'Active & Valid' : 'Token Expired (will auto-refresh)' }}
            </span>
          </div>
          <div v-if="connectionStatus.expires_at" class="detail-item">
            <span class="detail-label">Expires:</span>
            <span class="detail-value">{{ formatExpiration(connectionStatus.expires_at) }}</span>
          </div>
        </div>
      </div>

      <!-- Browser Token Setup (Recommended Method) -->
      <div v-if="!connectionStatus.connected" class="setup-section">
        <div class="setup-header">
          <svg class="setup-icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
          <div>
            <h4 class="setup-title">Manual Token Setup (Recommended)</h4>
            <p class="setup-subtitle">For H.265/1440p quality, you need a browser authentication token</p>
          </div>
        </div>

        <div class="info-box info-box-warning">
          <svg class="info-icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
          </svg>
          <div>
            <strong>Why browser token?</strong> Twitch restricts OAuth apps from accessing H.265/1440p streams. Only browser tokens grant full access.
          </div>
        </div>

        <div class="steps-container">
          <h5 class="steps-title">How to get your token:</h5>
          <ol class="steps-list">
            <li class="step-item">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>Open Twitch.tv</strong> in your browser and log in
              </div>
            </li>
            <li class="step-item">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>Press F12</strong> (or Ctrl+Shift+I) to open Developer Tools
              </div>
            </li>
            <li class="step-item">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>Go to Console tab</strong> and paste this code:
                <div class="code-block">
                  <code>document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]</code>
                  <button @click="copyTokenCommand" class="btn-copy" v-ripple title="Copy to clipboard">
                    <svg viewBox="0 0 24 24">
                      <path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                    </svg>
                  </button>
                </div>
              </div>
            </li>
            <li class="step-item">
              <span class="step-number">4</span>
              <div class="step-content">
                <strong>Copy the 30-character token</strong> (e.g., abc123xyz456...)
              </div>
            </li>
            <li class="step-item">
              <span class="step-number">5</span>
              <div class="step-content">
                <strong>Set it as environment variable</strong> in docker-compose.yml:
                <div class="code-block">
                  <code>TWITCH_OAUTH_TOKEN=your_token_here</code>
                </div>
              </div>
            </li>
          </ol>
        </div>

        <div class="info-box info-box-info">
          <svg class="info-icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/>
          </svg>
          <div>
            <strong>Token validity:</strong> Browser tokens last 60-90 days. You'll need to update it manually when it expires. The token is safe to store - it only works with your account.
          </div>
        </div>

        <div class="benefits-section">
          <h5 class="benefits-title">What you get with a browser token:</h5>
          <ul class="benefits-list">
            <li class="benefit-item">
              <svg class="benefit-icon" viewBox="0 0 24 24">
                <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span>H.265/HEVC and AV1 codecs (60% smaller files, same quality)</span>
            </li>
            <li class="benefit-item">
              <svg class="benefit-icon" viewBox="0 0 24 24">
                <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span>1440p60 recording (if stream supports it)</span>
            </li>
            <li class="benefit-item">
              <svg class="benefit-icon" viewBox="0 0 24 24">
                <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
              </svg>
              <span>Ad-free recordings (with Twitch Turbo subscription)</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- Action Buttons -->
      <div v-if="connectionStatus.connected" class="action-buttons">
        <button
          @click="refreshStatus"
          class="btn-action btn-secondary"
          :disabled="isLoading"
          v-ripple
        >
          <svg class="icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
          </svg>
          Refresh Status
        </button>
        
        <button
          @click="disconnectTwitch"
          class="btn-action btn-danger"
          :disabled="isLoading"
          v-ripple
        >
          <svg class="icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
          Clear Token
        </button>
      </div>
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'

interface ConnectionStatus {
  connected: boolean
  valid: boolean
  expires_at: string | null
}

const toast = useToast()

const connectionStatus = ref<ConnectionStatus>({
  connected: false,
  valid: false,
  expires_at: null
})

const isLoading = ref(false)
const callbackUrl = ref('')

const statusClass = computed(() => ({
  'status-connected': connectionStatus.value.connected && connectionStatus.value.valid,
  'status-warning': connectionStatus.value.connected && !connectionStatus.value.valid,
  'status-disconnected': !connectionStatus.value.connected
}))

const statusTitle = computed(() => {
  if (!connectionStatus.value.connected) return 'Not Connected (Optional)'
  if (!connectionStatus.value.valid) return 'Connected (Token Expiring)'
  return 'Connected to Twitch'
})

const statusDescription = computed(() => {
  if (!connectionStatus.value.connected) {
    return 'Browser token from environment is used for recordings. OAuth optional for follower sync.'
  }
  if (!connectionStatus.value.valid) {
    return 'Your token will be automatically refreshed on next recording'
  }
  return 'Your account is connected and tokens are valid'
})

onMounted(async () => {
  await fetchConnectionStatus()
  
  // Fetch callback URL for display
  try {
    const response = await fetch('/api/twitch/callback-url', {
      credentials: 'include'
    })
    
    if (response.ok) {
      const data = await response.json()
      callbackUrl.value = data.url || ''
    }
  } catch (error) {
    console.error('Failed to fetch callback URL:', error)
  }
  
  // Check if returning from OAuth success
  const urlParams = new URLSearchParams(window.location.search)
  if (urlParams.get('auth_success') === 'true') {
    toast.success('Twitch account connected successfully!')
    // Clean up URL
    window.history.replaceState({}, '', '/settings')
  } else if (urlParams.get('error') === 'auth_failed') {
    toast.error('Failed to connect Twitch account. Please try again.')
    window.history.replaceState({}, '', '/settings')
  }
})

async function fetchConnectionStatus() {
  try {
    const response = await fetch('/api/twitch/connection-status', {
      credentials: 'include'
    })
    
    if (response.ok) {
      connectionStatus.value = await response.json()
    }
  } catch (error) {
    console.error('Failed to fetch connection status:', error)
  }
}

async function _connectTwitch() {
  try {
    isLoading.value = true
    
    // Pass /settings as state parameter so backend knows where to redirect
    const response = await fetch('/api/twitch/auth-url?state=/settings', {
      credentials: 'include'
    })
    
    if (!response.ok) throw new Error('Failed to get auth URL')
    
    const data = await response.json()
    
    if (data.auth_url) {
      // Redirect to Twitch OAuth (state parameter tells backend to return to /settings)
      window.location.href = data.auth_url
    }
  } catch (error) {
    console.error('Failed to start Twitch OAuth:', error)
    toast.error('Could not connect to Twitch. Please try again.')
  } finally {
    isLoading.value = false
  }
}

async function disconnectTwitch() {
  if (!confirm('Are you sure you want to disconnect your Twitch account? You will lose access to H.265/1440p quality.')) {
    return
  }

  try {
    isLoading.value = true
    
    const response = await fetch('/api/twitch/disconnect', {
      method: 'POST',
      credentials: 'include'
    })
    
    if (!response.ok) throw new Error('Failed to disconnect')
    
    const data = await response.json()
    
    if (data.success) {
      connectionStatus.value = {
        connected: false,
        valid: false,
        expires_at: null
      }
      
      toast.success('Your Twitch account has been disconnected')
    }
  } catch (error) {
    console.error('Failed to disconnect Twitch:', error)
    toast.error('Could not disconnect from Twitch. Please try again.')
  } finally {
    isLoading.value = false
  }
}

async function refreshStatus() {
  isLoading.value = true
  await fetchConnectionStatus()
  isLoading.value = false
  
  toast.info('Connection status has been updated')
}

async function copyTokenCommand() {
  const command = `document.cookie.split("; ").find(item=>item.startsWith("auth-token="))?.split("=")[1]`
  
  try {
    await navigator.clipboard.writeText(command)
    toast.success('Command copied to clipboard!')
  } catch (error) {
    console.error('Failed to copy:', error)
    toast.error('Failed to copy. Please copy manually.')
  }
}

function formatExpiration(expiresAt: string): string {
  const date = new Date(expiresAt)
  const now = new Date()
  const diffMs = date.getTime() - now.getTime()
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60))
  
  if (diffHours > 0) {
    return `in ${diffHours}h ${diffMinutes}m`
  } else if (diffMinutes > 0) {
    return `in ${diffMinutes}m`
  } else {
    return 'Expired (will auto-refresh)'
  }
}
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// TWITCH CONNECTION PANEL - Unified Design
// Most styles inherited from global _settings-panels.scss
// ============================================================================

// ============================================================================
// CONNECTION STATUS
// ============================================================================

.connection-status {
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  padding: v.$spacing-4;
  background: var(--background-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: v.$spacing-6;
  
  &.connected {
    border-color: var(--success-color);
    background: var(--success-bg-color);
  }
  
  &.disconnected {
    border-color: var(--danger-color);
    background: var(--danger-bg-color);
  }
  
  .status-indicator {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--danger-color);
    flex-shrink: 0;
    
    &.connected {
      background: var(--success-color);
      animation: pulse 2s infinite;
    }
  }
  
  .status-text {
    flex: 1;
    
    .status-title {
      font-weight: v.$font-semibold;
      color: var(--text-primary);
      margin-bottom: v.$spacing-1;
    }
    
    .status-description {
      font-size: v.$text-sm;
      color: var(--text-secondary);
    }
  }
}

.status-header {
  display: flex;
  align-items: center;
  gap: v.$spacing-3;
  margin-bottom: v.$spacing-4;
}

.status-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  flex-shrink: 0;
  
  &.status-connected {
    background: rgba(var(--success-color-rgb, 46, 213, 115), 0.1);
    color: var(--success-color);
  }
  
  &.status-warning {
    background: rgba(var(--warning-color-rgb, 255, 165, 2), 0.1);
    color: var(--warning-color);
  }
  
  &.status-disconnected {
    background: rgba(var(--danger-color-rgb, 255, 71, 87), 0.1);
    color: var(--danger-color);
  }
}

.status-icon {
  width: 28px;
  height: 28px;
}

.status-info {
  flex: 1;
}

.status-title {
  font-size: v.$text-lg;
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0 0 v.$spacing-1 0;
}

.status-description {
  font-size: v.$text-sm;
  color: var(--text-secondary);
  margin: 0;
}

.connection-details {
  margin-top: v.$spacing-3;
  padding: v.$spacing-3;
  background: rgba(var(--primary-color-rgb, 66, 184, 131), 0.05);
  border-radius: var(--radius-md);
}

.detail-item {
  display: flex;
  justify-content: space-between;
  font-size: v.$text-sm;
  
  &:not(:last-child) {
    margin-bottom: v.$spacing-2;
  }
}

.detail-label {
  color: var(--text-secondary);
  font-weight: v.$font-medium;
}

.detail-value {
  color: var(--text-primary);
  font-weight: v.$font-semibold;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

// ============================================================================
// TOKEN SETUP GUIDE
// ============================================================================

.setup-section {
  margin-top: v.$spacing-6;
}

.setup-header {
  display: flex;
  align-items: flex-start;
  gap: v.$spacing-3;
  margin-bottom: v.$spacing-4;
}

.setup-icon {
  width: 32px;
  height: 32px;
  color: var(--success-color);
  flex-shrink: 0;
}

.setup-title {
  font-size: v.$text-lg;
  font-weight: v.$font-semibold;
  color: var(--text-primary);
  margin: 0 0 v.$spacing-1 0;
}

.setup-subtitle {
  font-size: v.$text-sm;
  color: var(--text-secondary);
  margin: 0;
}

.info-box {
  display: flex;
  align-items: flex-start;
  gap: v.$spacing-3;
  padding: v.$spacing-4;
  background: var(--info-bg-color);
  border: 1px solid var(--info-border-color);
  border-radius: var(--radius-md);
  margin: v.$spacing-4 0;
  
  &.info-box-warning {
    background: rgba(var(--warning-color-rgb, 255, 165, 2), 0.1);
    border-color: var(--warning-color);
  }
  
  &.info-box-info {
    background: rgba(var(--info-color-rgb, 112, 161, 255), 0.1);
    border-color: var(--info-color);
  }
  
  &.info-box-success {
    background: rgba(var(--success-color-rgb, 46, 213, 115), 0.1);
    border-color: var(--success-color);
  }
}

.info-icon {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  color: currentColor;
}

.token-setup-guide {
  .setup-steps {
    list-style: none;
    counter-reset: step-counter;
    padding: 0;
    
    li {
      counter-increment: step-counter;
      position: relative;
      padding-left: v.$spacing-10;
      margin-bottom: v.$spacing-4;
      
      &:before {
        content: counter(step-counter);
        position: absolute;
        left: 0;
        top: 0;
        width: 32px;
        height: 32px;
        background: var(--primary-color);
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: v.$font-bold;
        font-size: v.$text-sm;
      }
      
      strong {
        color: var(--text-primary);
        display: block;
        margin-bottom: v.$spacing-1;
      }
    }
  }
  
  .code-snippet {
    background: var(--background-darker);
    padding: v.$spacing-3;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: v.$text-sm;
    color: var(--primary-color);
    overflow-x: auto;
    margin: v.$spacing-2 0;
    
    code {
      white-space: pre;
      display: block;
    }
  }
  
  .copy-button {
    margin-left: v.$spacing-2;
    padding: v.$spacing-1 v.$spacing-2;
    font-size: v.$text-xs;
  }
}

// Steps Container
.steps-container {
  padding: var(--spacing-4);
  background: transparent;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.steps-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-4) 0;
}

.steps-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.step-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
}

.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--gradient-primary);
  color: white;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-bold);
  flex-shrink: 0;
}

.step-content {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.quality-benefits {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: v.$spacing-3;
  margin-top: v.$spacing-4;
  
  .benefit-item {
    padding: v.$spacing-3;
    background: var(--background-hover);
    border-radius: var(--radius-sm);
    
    .benefit-icon {
      font-size: v.$text-xl;
      color: var(--success-color);
      margin-bottom: v.$spacing-2;
    }
    
    .benefit-title {
      font-weight: v.$font-semibold;
      color: var(--text-primary);
      margin-bottom: v.$spacing-1;
    }
    
    .benefit-description {
      font-size: v.$text-sm;
      color: var(--text-secondary);
    }
  }
}

.code-block {
  position: relative;
  margin-top: var(--spacing-2);
  padding: var(--spacing-3);
  background: transparent;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 12px;
  overflow-x: auto;

  code {
    color: var(--text-primary);
    word-break: break-all;
  }
}

.btn-copy {
  position: absolute;
  top: var(--spacing-2);
  right: var(--spacing-2);
  padding: var(--spacing-2);
  background: var(--background-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background: var(--background-hover);
    border-color: var(--primary-color);
  }
  
  svg {
    width: 16px;
    height: 16px;
    display: block;
  }
}

// Benefits Section
.benefits-section {
  padding: var(--spacing-4);
  background: transparent;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.benefits-title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-3);
}

.benefits-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.benefit-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.benefit-icon {
  width: 16px;
  height: 16px;
  fill: var(--color-primary);
  flex-shrink: 0;
  margin-top: 2px;
}

// Action Buttons
.action-buttons {
  display: flex;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-5);
  border-radius: var(--radius-lg);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid;

  .icon {
    width: 16px;
    height: 16px;
  }
  
  .info-content {
    font-size: v.$text-sm;
    color: var(--text-secondary);
    line-height: 1.6;
  }
}

// ============================================================================
// RESPONSIVE
// ============================================================================

@include m.respond-below('md') {
  .connection-status {
    flex-direction: column;
    text-align: center;
    padding: v.$spacing-3;
    margin-bottom: v.$spacing-4;
  }
  
  .form-actions {
    flex-direction: column;
    
    .btn {
      width: 100%;
    }
  }
}

@include m.respond-below('sm') {
  // Reduce padding in nested cards on mobile
  .token-guide {
    padding: v.$spacing-3;
  }
  
  .guide-steps ol {
    padding-left: v.$spacing-4;
  }
  
  .info-banner,
  .warning-banner {
    padding: v.$spacing-3;
  }
}
</style>
