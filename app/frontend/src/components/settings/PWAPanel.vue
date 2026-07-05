<template>
  <div class="pwa-panel">
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

      <div v-if="pushSupported" class="pwa-push-notifications">
        <div class="setting-item settings-item">
          <div class="setting-info settings-item__info">
            <label>Notification Permission</label>
            <p class="setting-description">
              <template v-if="notificationPermission === 'default'">
                Push notifications allow StreamVault to send alerts for stream events even when the app is not open. Enable this to receive real-time updates about your streamers.
              </template>
              <template v-else-if="notificationPermission === 'denied'">
                Notification permission was denied in your browser. You will need to reset this in your browser settings or site permissions to enable push notifications.
              </template>
              <template v-else>
                Notification permission is granted. You can manage your subscription below.
              </template>
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
          </div>
        </div>

        <div v-if="notificationPermission === 'denied'" class="pwa-permission-denied">
          <div class="setting-item settings-item">
            <div class="setting-info settings-item__info">
              <label>Troubleshooting</label>
              <p class="setting-description">
                To enable push notifications, update your browser's site permissions for StreamVault to allow notifications. After changing the permission, refresh this page and click Enable Notifications below.
              </p>
            </div>
          </div>
        </div>

        <div class="setting-item settings-item">
          <div class="setting-info settings-item__info">
            <label>Push Subscription</label>
            <p class="setting-description">
              <template v-if="pushState === 'checking'">Checking your push subscription status...</template>
              <template v-else-if="pushState === 'subscribed'">You are subscribed to push notifications.</template>
              <template v-else-if="pushState === 'subscribing'">Setting up push subscription...</template>
              <template v-else-if="pushState === 'error'">There was an issue with your push subscription.</template>
              <template v-else>You are not subscribed to push notifications.</template>
            </p>
          </div>
          <div class="setting-control settings-item__actions">
            <span class="status-badge" :class="{
              'granted': pushState === 'subscribed',
              'denied': pushState === 'error',
              'default': pushState === 'unsubscribed' || pushState === 'checking' || pushState === 'subscribing'
            }">
              {{ pushStateText }}
            </span>
            <button
              v-if="pushState === 'unsubscribed' && notificationPermission !== 'denied'"
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
              v-if="pushState === 'subscribed'"
              @click="disableNotifications"
              class="btn btn-secondary"
              :disabled="isDisablingNotifications"
            >
              <svg class="icon" aria-hidden="true">
                <use xlink:href="#icon-bell-off"></use>
              </svg>
              {{ isDisablingNotifications ? 'Disabling...' : 'Disable Notifications' }}
            </button>
            <button
              v-if="pushState === 'error' && notificationPermission !== 'denied'"
              @click="enableNotifications"
              class="btn btn-primary"
              :disabled="isEnablingNotifications"
            >
              {{ isEnablingNotifications ? 'Retrying...' : 'Retry' }}
            </button>
          </div>
        </div>

        <div v-if="pushError && pushState === 'error'" class="setting-item settings-item">
          <div class="setting-info settings-item__info">
            <label>Error Details</label>
            <p class="setting-description pwa-error-message">
              {{ pushError }}
            </p>
          </div>
        </div>

        <div v-if="notificationPermission === 'granted' && pushState === 'subscribed'" class="setting-item settings-item">
          <div class="setting-info settings-item__info">
            <label>Delivery Test</label>
            <p class="setting-description">
              Push tests are available in Admin Diagnostics so routine settings stay focused on user preferences.
            </p>
          </div>
        </div>
      </div>
    </div>

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

    <div v-if="statusMessage" class="status-message" :class="statusType" role="status">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { usePWA } from '@/composables/usePWA'

const {
  isInstallable,
  isInstalled,
  isOnline,
  pushSupported,
  notificationPermission,
  pushState,
  pushError,
  installPWA,
  subscribeToPush,
  unsubscribeFromPush,
  requestNotificationPermission
} = usePWA()

const isEnablingNotifications = ref(false)
const isDisablingNotifications = ref(false)
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

const pushStateText = computed(() => {
  switch (pushState.value) {
    case 'subscribed': return 'Subscribed'
    case 'unsubscribed': return 'Not Subscribed'
    case 'checking': return 'Checking...'
    case 'subscribing': return 'Subscribing...'
    case 'error': return 'Error'
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

const showStatus = (message: string, type: 'success' | 'error' | 'info') => {
  statusMessage.value = message
  statusType.value = type

  setTimeout(() => {
    statusMessage.value = ''
    statusType.value = ''
  }, 5000)
}

</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

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

.pwa-permission-denied {
  margin-top: v.$spacing-2;
}

.pwa-error-message {
  color: var(--error-color);
}

@include m.respond-below('md') {
  .form-actions {
    flex-direction: column;

    .btn {
      width: 100%;
    }
  }

  .setting-item .setting-control {
    width: 100%;

    .btn {
      width: 100%;
    }
  }
}
</style>
