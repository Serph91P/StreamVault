<template>
  <GlassCard>
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

      <!-- Benefits Info -->
      <div v-if="!connectionStatus.connected" class="benefits-section">
        <h4 class="benefits-title">Benefits of Connecting:</h4>
        <ul class="benefits-list">
          <li class="benefit-item">
            <svg class="benefit-icon">
              <use href="#icon-check" />
            </svg>
            <span>Access to H.265/HEVC and AV1 codecs (better quality, smaller files)</span>
          </li>
          <li class="benefit-item">
            <svg class="benefit-icon">
              <use href="#icon-check" />
            </svg>
            <span>1440p recording quality (requires Twitch Partner/Turbo)</span>
          </li>
          <li class="benefit-item">
            <svg class="benefit-icon">
              <use href="#icon-check" />
            </svg>
            <span>Ad-free recordings if you have Twitch Turbo</span>
          </li>
          <li class="benefit-item">
            <svg class="benefit-icon">
              <use href="#icon-check" />
            </svg>
            <span>Automatic token refresh (no manual updates needed)</span>
          </li>
        </ul>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button
          v-if="!connectionStatus.connected"
          @click="connectTwitch"
          class="btn-action btn-primary"
          :disabled="isLoading"
          v-ripple
        >
          <svg class="icon" viewBox="0 0 24 24">
            <path fill="currentColor" d="M11.64 5.93H13.07V10.21H11.64M15.57 5.93H17V10.21H15.57M7 2L3.43 5.57V18.43H7.71V22L11.29 18.43H14.14L20.57 12V2M19.14 11.29L16.29 14.14H13.43L10.93 16.64V14.14H7.71V3.43H19.14Z"/>
          </svg>
          Connect with Twitch
        </button>

        <button
          v-else
          @click="disconnectTwitch"
          class="btn-action btn-secondary"
          :disabled="isLoading"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-x" />
          </svg>
          Disconnect
        </button>

        <button
          v-if="connectionStatus.connected"
          @click="refreshStatus"
          class="btn-action btn-secondary"
          :disabled="isLoading"
          v-ripple
        >
          <svg class="icon">
            <use href="#icon-refresh-cw" />
          </svg>
          Refresh Status
        </button>
      </div>
    </div>
  </GlassCard>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import GlassCard from '@/components/cards/GlassCard.vue'
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
  if (!connectionStatus.value.connected) return 'Not Connected'
  if (!connectionStatus.value.valid) return 'Connected (Token Expiring)'
  return 'Connected to Twitch'
})

const statusDescription = computed(() => {
  if (!connectionStatus.value.connected) {
    return 'Connect your Twitch account for better quality and features'
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

async function connectTwitch() {
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
.card-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

// Connection Status
.connection-status {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.status-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
}

.status-icon-wrapper {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-xl);
  flex-shrink: 0;
  transition: all 0.3s ease;

  &.status-connected {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(21, 128, 61, 0.15) 100%);

    .status-icon {
      fill: #22c55e;
    }
  }

  &.status-warning {
    background: linear-gradient(135deg, rgba(251, 191, 36, 0.15) 0%, rgba(217, 119, 6, 0.15) 100%);

    .status-icon {
      fill: #fbbf24;
    }
  }

  &.status-disconnected {
    background: linear-gradient(135deg, rgba(148, 163, 184, 0.15) 0%, rgba(100, 116, 139, 0.15) 100%);

    .status-icon {
      fill: #94a3b8;
    }
  }
}

.status-icon {
  width: 32px;
  height: 32px;
}

.status-info {
  flex: 1;
}

.status-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
}

.status-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.connection-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding: var(--spacing-4);
  background: var(--background-secondary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--font-size-sm);
}

.detail-label {
  color: var(--text-secondary);
  font-weight: var(--font-weight-medium);
}

.detail-value {
  color: var(--text-primary);
  font-weight: var(--font-weight-semibold);

  &.text-success {
    color: #22c55e;
  }

  &.text-warning {
    color: #fbbf24;
  }
}

// Benefits Section
.benefits-section {
  padding: var(--spacing-4);
  background: var(--background-tertiary);
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

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  &.btn-primary {
    background: var(--gradient-primary);
    color: white;
    border-color: transparent;

    &:not(:disabled):hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-lg);
    }
  }

  &.btn-secondary {
    background: var(--background-secondary);
    color: var(--text-primary);
    border-color: var(--border-color);

    &:not(:disabled):hover {
      border-color: var(--color-primary);
      background: rgba(var(--color-primary-rgb), 0.05);
    }
  }
}
</style>
