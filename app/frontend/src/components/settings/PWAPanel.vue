<template>
  <div class="pwa-panel">
    <!-- PWA Installation -->
    <div class="pwa-section settings-section">
      <h4>Progressive Web App</h4>
      
      <div class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Installation Status</label>
          <p class="setting-description">
            {{ isInstalled ? 'StreamVault is installed as an app' : 'StreamVault can be installed as an app for better experience' }}
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge" :class="{ 'installed': isInstalled, 'not-installed': !isInstalled }">
            {{ isInstalled ? 'Installed' : 'Not Installed' }}
          </span>
          <button 
            v-if="isInstallable && !isInstalled" 
            @click="installApp" 
            class="btn btn-primary install-btn"
          >
            Install App
          </button>
        </div>
      </div>

      <div class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Connection Status</label>
          <p class="setting-description">
            {{ isOnline ? 'You are currently online' : 'You are currently offline' }}
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge" :class="{ 'online': isOnline, 'offline': !isOnline }">
            {{ isOnline ? 'Online' : 'Offline' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Push Notifications -->
    <div class="pwa-section settings-section">
      <h4>Push Notifications</h4>
      
      <div class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Browser Support</label>
          <p class="setting-description">
            {{ pushSupported ? 'Your browser supports push notifications' : 'Your browser does not support push notifications' }}
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge" :class="{ 'supported': pushSupported, 'not-supported': !pushSupported }">
            {{ pushSupported ? 'Supported' : 'Not Supported' }}
          </span>
        </div>
      </div>

      <div class="setting-item settings-item" v-if="pushSupported">
        <div class="setting-info settings-item__info">
          <label>Notification Permission</label>
          <p class="setting-description">
            Allow StreamVault to send push notifications for stream events
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge" :class="{
            'granted': notificationPermission === 'granted',
            'denied': notificationPermission === 'denied',
            'default': notificationPermission === 'default'
          }">
            {{ permissionText }}
          </span>
          <button 
            v-if="notificationPermission !== 'granted'" 
            @click="enableNotifications" 
            class="btn btn-primary"
            :disabled="isEnablingNotifications"
          >
            <svg class="icon" aria-hidden="true">
              <use xlink:href="#icon-bell"></use>
            </svg>
            {{ isEnablingNotifications ? 'Enabling...' : 'Enable Notifications' }}
          </button>
          <button 
            v-else 
            @click="disableNotifications" 
            class="btn btn-secondary"
            :disabled="isDisablingNotifications"
          >
            <svg class="icon" aria-hidden="true">
              <use xlink:href="#icon-bell-off"></use>
            </svg>
            {{ isDisablingNotifications ? 'Disabling...' : 'Disable Notifications' }}
          </button>
        </div>
      </div>

      <div class="setting-item settings-item" v-if="notificationPermission === 'granted'">
        <div class="setting-info settings-item__info">
          <label>Test Notification</label>
          <p class="setting-description">
            Send a test push notification to verify everything is working
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <button 
            @click="sendTestNotification" 
            class="btn btn-secondary"
            :disabled="isSendingTest"
          >
            <svg class="icon" aria-hidden="true">
              <use xlink:href="#icon-send"></use>
            </svg>
            {{ isSendingTest ? 'Sending...' : 'Send Test' }}
          </button>
          <button 
            @click="sendLocalTestNotification" 
            class="btn btn-primary btn-spacing"
          >
            <svg class="icon" aria-hidden="true">
              <use xlink:href="#icon-smartphone"></use>
            </svg>
            Test Local
          </button>
        </div>
      </div>
    </div>

    <!-- PWA Features -->
    <div class="pwa-section settings-section">
      <h4>App Features</h4>
      
      <div class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Offline Support</label>
          <p class="setting-description">
            Basic app functionality works offline with cached content
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge supported">Enabled</span>
        </div>
      </div>

      <div class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Background Sync</label>
          <p class="setting-description">
            Sync data automatically when connection is restored
          </p>
        </div>
        <div class="setting-control settings-item__actions">
          <span class="status-badge supported">Enabled</span>
        </div>
      </div>
    </div>

    <!-- Success/Error Messages -->
    <div v-if="statusMessage" class="status-message" :class="statusType">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePWA } from '@/composables/usePWA'

const {
  isInstallable,
  isInstalled,
  isOnline,
  pushSupported,
  notificationPermission,
  installPWA,
  subscribeToPush,
  unsubscribeFromPush,
  showNotification,
  requestNotificationPermission
} = usePWA()

const isEnablingNotifications = ref(false)
const isDisablingNotifications = ref(false)
const isSendingTest = ref(false)
const statusMessage = ref('')
const statusType = ref('')

const permissionText = computed(() => {
  switch (notificationPermission.value) {
    case 'granted': return 'Granted'
    case 'denied': return 'Denied'
    case 'default': return 'Not Asked'
    default: return 'Unknown'
  }
})

const installApp = async () => {
  try {
    await installPWA()
    showStatus('App installation initiated', 'success')
  } catch (error) {
    console.error('App installation failed:', error)
    showStatus('App installation failed', 'error')
  }
}

const enableNotifications = async () => {
  try {
    isEnablingNotifications.value = true
    
    const permission = await requestNotificationPermission()
    
    if (permission === 'granted') {
      const subscription = await subscribeToPush()
      if (subscription) {
        showStatus('Push notifications enabled successfully', 'success')
      } else {
        showStatus('Failed to enable push notifications', 'error')
      }
    } else {
      showStatus('Notification permission denied', 'error')
    }
  } catch (error) {
    console.error('Failed to enable notifications:', error)
    showStatus('Failed to enable notifications', 'error')
  } finally {
    isEnablingNotifications.value = false
  }
}

const disableNotifications = async () => {
  try {
    isDisablingNotifications.value = true
    
    const success = await unsubscribeFromPush()
    if (success) {
      showStatus('Push notifications disabled', 'success')
    } else {
      showStatus('Failed to disable push notifications', 'error')
    }
  } catch (error) {
    console.error('Failed to disable notifications:', error)
    showStatus('Failed to disable notifications', 'error')
  } finally {
    isDisablingNotifications.value = false
  }
}

const sendTestNotification = async () => {
  try {
    isSendingTest.value = true
    
    // Try server-side push notification first
    const response = await fetch('/api/push/test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    if (response.ok) {
      const result = await response.json()
      if (result.success && result.sent_count > 0) {
        showStatus(result.message, 'success')
        return
      } else {
        console.warn('Server push failed:', result.message)
        // Fall through to local notification
      }
    }
    
    // If server push fails, try local notification via Service Worker

    
    try {
      await showNotification('🧪 StreamVault Test (Local)', {
        body: 'This is a local test notification. If you see this, your browser supports notifications!',
        icon: '/android-icon-192x192.png',
        badge: '/android-icon-96x96.png',
        tag: 'test-local-notification',
        requireInteraction: true,
        data: {
          type: 'test_local',
          timestamp: Date.now()
        }
      })
      
      showStatus('Local test notification sent successfully', 'success')
      
    } catch (localError) {
      console.error('Local notification also failed:', localError)
      
      // Try browser native notification as last resort
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('🧪 StreamVault Test (Native)', {
          body: 'This is a native browser notification. Notifications are working!',
          icon: '/android-icon-192x192.png',
          tag: 'test-native-notification'
        })
        showStatus('Native test notification sent successfully', 'success')
      } else {
        throw new Error('All notification methods failed')
      }
    }
    
  } catch (error) {
    console.error('Failed to send test notification:', error)
    showStatus('Failed to send test notification. Check console for details.', 'error')
  } finally {
    isSendingTest.value = false
  }
}

const showStatus = (message: string, type: 'success' | 'error' | 'info') => {
  statusMessage.value = message
  statusType.value = type
  
  // Clear message after 5 seconds
  setTimeout(() => {
    statusMessage.value = ''
    statusType.value = ''
  }, 5000)
}

const sendLocalTestNotification = async () => {
  try {
    // Try local notification to test PWA functionality
    if ('serviceWorker' in navigator && 'Notification' in window) {
      const permission = await requestNotificationPermission()
      if (permission === 'granted') {
        const notificationOptions: any = {
          body: 'This is a local PWA test notification. If you see this, your PWA notifications are working!',
          icon: '/android-icon-192x192.png',
          badge: '/android-icon-96x96.png',
          tag: 'pwa-test',
          requireInteraction: true,
          vibrate: [200, 100, 200],
          actions: [
            {
              action: 'close',
              title: 'Close'
            }
          ]
        }
        
        await showNotification('🧪 StreamVault PWA Test', notificationOptions)
        showStatus('Local PWA notification sent! Check your device.', 'success')
      } else {
        showStatus('Notification permission not granted', 'error')
      }
    } else {
      showStatus('PWA features not supported in this browser', 'error')
    }
  } catch (error) {
    console.error('Local test notification failed:', error)
    showStatus('Local test notification failed', 'error')
  }
}

onMounted(() => {
  // Any initialization logic
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

// ============================================================================
// PWA PANEL - Unified Design
// Most styles inherited from global _settings-panels.scss
// ============================================================================

// ============================================================================
// PWA STATUS CARDS
// ============================================================================

.pwa-status {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: v.$spacing-4;
  margin-bottom: v.$spacing-6;
  
  @include m.respond-below('sm') {
    grid-template-columns: 1fr;
  }
}

.status-card {
  padding: v.$spacing-4;
  background: var(--background-card);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  
  &.installed {
    border-color: var(--success-color);
    background: var(--success-bg-color);
  }
  
  &.not-installed {
    border-color: var(--warning-color);
    background: var(--warning-bg-color);
  }
  
  .status-icon {
    font-size: v.$text-3xl;
    margin-bottom: v.$spacing-2;
  }
  
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

// ============================================================================
// INSTALL INSTRUCTIONS
// ============================================================================

.install-instructions {
  .platform-tabs {
    display: flex;
    gap: v.$spacing-2;
    margin-bottom: v.$spacing-4;
    border-bottom: 2px solid var(--border-color);
    
    @include m.respond-below('sm') {
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }
    
    .platform-tab {
      padding: v.$spacing-3 v.$spacing-4;
      background: transparent;
      border: none;
      border-bottom: 3px solid transparent;
      color: var(--text-secondary);
      cursor: pointer;
      transition: v.$transition-all;
      white-space: nowrap;
      
      &:hover {
        color: var(--text-primary);
        background: var(--background-hover);
      }
      
      &.active {
        color: var(--primary-color);
        border-bottom-color: var(--primary-color);
        font-weight: v.$font-semibold;
      }
    }
  }
  
  .instruction-steps {
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
      
      span {
        color: var(--text-secondary);
        font-size: v.$text-sm;
      }
    }
  }
}

// ============================================================================
// FEATURES LIST
// ============================================================================

.pwa-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: v.$spacing-3;
  margin-top: v.$spacing-6;
  
  .feature-item {
    display: flex;
    align-items: center;
    gap: v.$spacing-2;
    padding: v.$spacing-3;
    background: var(--background-hover);
    border-radius: var(--radius-sm);
    
    .feature-icon {
      font-size: v.$text-xl;
      color: var(--primary-color);
    }
    
    .feature-text {
      font-size: v.$text-sm;
      color: var(--text-primary);
    }
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
}
</style>
