<template>
  <div class="pwa-panel">
    <div class="section-header">
      <h3>PWA & Notifications</h3>
      <p>Configure Progressive Web App features and push notifications</p>
    </div>

    <!-- PWA Installation -->
    <div class="pwa-section">
      <h4>Progressive Web App</h4>
      
      <div class="setting-item">
        <div class="setting-info">
          <label>Installation Status</label>
          <p class="setting-description">
            {{ isInstalled ? 'StreamVault is installed as an app' : 'StreamVault can be installed as an app for better experience' }}
          </p>
        </div>
        <div class="setting-control">
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

      <div class="setting-item">
        <div class="setting-info">
          <label>Connection Status</label>
          <p class="setting-description">
            {{ isOnline ? 'You are currently online' : 'You are currently offline' }}
          </p>
        </div>
        <div class="setting-control">
          <span class="status-badge" :class="{ 'online': isOnline, 'offline': !isOnline }">
            {{ isOnline ? 'Online' : 'Offline' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Push Notifications -->
    <div class="pwa-section">
      <h4>Push Notifications</h4>
      
      <div class="setting-item">
        <div class="setting-info">
          <label>Browser Support</label>
          <p class="setting-description">
            {{ pushSupported ? 'Your browser supports push notifications' : 'Your browser does not support push notifications' }}
          </p>
        </div>
        <div class="setting-control">
          <span class="status-badge" :class="{ 'supported': pushSupported, 'not-supported': !pushSupported }">
            {{ pushSupported ? 'Supported' : 'Not Supported' }}
          </span>
        </div>
      </div>

      <div class="setting-item" v-if="pushSupported">
        <div class="setting-info">
          <label>Notification Permission</label>
          <p class="setting-description">
            Allow StreamVault to send push notifications for stream events
          </p>
        </div>
        <div class="setting-control">
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

      <div class="setting-item" v-if="notificationPermission === 'granted'">
        <div class="setting-info">
          <label>Test Notification</label>
          <p class="setting-description">
            Send a test push notification to verify everything is working
          </p>
        </div>
        <div class="setting-control">
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
    <div class="pwa-section">
      <h4>App Features</h4>
      
      <div class="setting-item">
        <div class="setting-info">
          <label>Offline Support</label>
          <p class="setting-description">
            Basic app functionality works offline with cached content
          </p>
        </div>
        <div class="setting-control">
          <span class="status-badge supported">Enabled</span>
        </div>
      </div>

      <div class="setting-item">
        <div class="setting-info">
          <label>Background Sync</label>
          <p class="setting-description">
            Sync data automatically when connection is restored
          </p>
        </div>
        <div class="setting-control">
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

<style scoped>
.pwa-panel {
  max-width: 800px;
}

.section-header {
  margin-bottom: 2rem;
}

.section-header h3 {
  margin: 0 0 0.5rem 0;
  color: var(--text-color);
  font-size: 1.5rem;
  font-weight: 600;
}

.section-header p {
  margin: 0;
  color: var(--text-muted-color);
  font-size: 0.95rem;
}

.pwa-section {
  background: var(--card-background);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.pwa-section h4 {
  margin: 0 0 1.5rem 0;
  color: var(--text-color);
  font-size: 1.25rem;
  font-weight: 600;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1rem 0;
  border-bottom: 1px solid var(--border-color);
}

.setting-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.setting-info {
  flex: 1;
  margin-right: 1rem;
}

.setting-info label {
  display: block;
  font-weight: 600;
  color: var(--text-color);
  margin-bottom: 0.25rem;
}

.setting-description {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-muted-color);
  line-height: 1.4;
}

.setting-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-badge.installed,
.status-badge.granted,
.status-badge.online,
.status-badge.supported {
  background: var(--success-color, #28a745);
  color: white;
}

.status-badge.not-installed,
.status-badge.denied,
.status-badge.offline,
.status-badge.not-supported {
  background: var(--danger-color, #dc3545);
  color: white;
}

.status-badge.default {
  background: var(--warning-color, #ffc107);
  color: var(--dark-color, #212529);
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: var(--radius-lg, 8px);
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 40px;  /* Touch-friendly */
}

.btn .icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.btn-spacing {
  margin-left: 0.5rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn.btn-primary {
  background: var(--primary-color, #6f42c1);
  color: white;
}

.btn.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover-color, #5a2d91);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(111, 66, 193, 0.3);
}

.btn.btn-secondary {
  background: var(--background-card, #3a3a3a);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn.btn-secondary:hover:not(:disabled) {
  background: var(--background-darker, #2a2a2a);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.btn:active:not(:disabled) {
  transform: translateY(0);
}

.install-btn {
  font-size: 0.8rem;
  padding: 0.4rem 0.8rem;
}

.status-message {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  border-radius: 4px;
  font-weight: 500;
}

.status-message.success {
  background: var(--success-bg-color, #d4edda);
  color: var(--success-text-color, #155724);
  border: 1px solid var(--success-border-color, #c3e6cb);
}

.status-message.error {
  background: var(--danger-bg-color, #f8d7da);
  color: var(--danger-text-color, #721c24);
  border: 1px solid var(--danger-border-color, #f5c6cb);
}

.status-message.info {
  background: var(--info-bg-color, #d1ecf1);
  color: var(--info-text-color, #0c5460);
  border: 1px solid var(--info-border-color, #bee5eb);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .setting-item {
    flex-direction: column;
    align-items: stretch;
  }
  
  .setting-info {
    margin-right: 0;
    margin-bottom: 1rem;
  }
  
  .setting-control {
    justify-content: space-between;
  }
  
  .btn {
    padding: 0.75rem 1rem;
    font-size: 1rem;
  }
}
</style>
