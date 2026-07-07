<template>
  <div class="pwa-panel">
    <div class="pwa-section settings-section">
      <h4>Progressive Web App</h4>

      <div class="pwa-flow-card">
        <div class="pwa-flow-card__step">1</div>
        <div>
          <h5>Install the mobile app shell</h5>
          <p>
            Add StreamVault to your home screen for full-height mobile browsing, app switching, and cached shell access.
          </p>
        </div>
      </div>

      <div class="pwa-guide-card">
        <div>
          <strong>{{ installGuideTitle }}</strong>
          <p>{{ installGuideDescription }}</p>
        </div>
        <button
          v-if="!isInstalled"
          class="btn btn-secondary"
          type="button"
          @click="showInstallGuide = !showInstallGuide"
        >
          {{ showInstallGuide ? 'Hide setup guide' : 'Show setup guide' }}
        </button>
      </div>

      <div v-if="showInstallGuide && !isInstalled" class="pwa-primer-details">
        <ul>
          <li v-for="step in installInstructions.steps" :key="step">{{ step }}</li>
        </ul>
        <p v-if="!pwaCriteria.allCriteriaMet" class="pwa-guide-note">
          Some install prerequisites are unavailable in this browser session. Use HTTPS or localhost and keep the service worker enabled.
        </p>
      </div>

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
            :disabled="isInstallingApp"
          >
            {{ isInstallingApp ? 'Opening...' : 'Install App' }}
          </button>
        </div>
      </div>

      <div v-if="installError" class="setting-item settings-item">
        <div class="setting-info settings-item__info">
          <label>Install Help</label>
          <p class="setting-description pwa-error-message">
            {{ installError }}
          </p>
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

      <div class="pwa-flow-card pwa-flow-card--permission">
        <div class="pwa-flow-card__step">2</div>
        <div>
          <h5>Choose notification behavior first</h5>
          <p>
            StreamVault only asks the browser permission after you review what alerts are for. No surprise permission prompt is shown on page load.
          </p>
        </div>
      </div>

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

        <div v-if="notificationPermission === 'default'" class="pwa-primer-card">
          <div>
            <strong>Before allowing notifications</strong>
            <p>
              You will receive browser push alerts for streamer activity and recording status. You can disable them here later.
            </p>
          </div>
          <button
            class="btn btn-secondary"
            type="button"
            @click="showPushPrimer = !showPushPrimer"
          >
            {{ showPushPrimer ? 'Hide details' : 'Review details' }}
          </button>
        </div>

        <div v-if="showPushPrimer && notificationPermission === 'default'" class="pwa-primer-details">
          <ul>
            <li>Browser permission is requested only after you press Allow notifications below.</li>
            <li>If you deny it, StreamVault shows recovery instructions instead of asking again.</li>
            <li>Push subscriptions are synced with the server only after permission is granted.</li>
          </ul>
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
              @click="handleNotificationPrimaryAction"
              class="btn btn-primary"
              :disabled="isEnablingNotifications"
            >
              <svg class="icon" aria-hidden="true">
                <use xlink:href="#icon-bell"></use>
              </svg>
              {{ enableNotificationsLabel }}
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
              @click="handleNotificationPrimaryAction"
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

      <div v-else class="pwa-primer-details">
        Push notifications need service worker and Push API support. You can still use StreamVault, but browser push alerts are unavailable in this browser.
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
  installError,
  installPWA,
  subscribeToPush,
  unsubscribeFromPush,
  requestNotificationPermission,
  checkPWAInstallCriteria,
  getInstallInstructions
} = usePWA()

const isEnablingNotifications = ref(false)
const isDisablingNotifications = ref(false)
const isInstallingApp = ref(false)
const showInstallGuide = ref(false)
const showPushPrimer = ref(false)
const statusMessage = ref('')
const statusType = ref('')

const installInstructions = computed(() => getInstallInstructions())
const pwaCriteria = computed(() => checkPWAInstallCriteria())

const installGuideTitle = computed(() => {
  if (isInstalled.value) return 'StreamVault is already installed'
  if (isInstallable.value) return 'Ready to install'
  if (!pwaCriteria.value.allCriteriaMet) return 'Install prerequisites need attention'
  return 'Manual install steps are available'
})

const installGuideDescription = computed(() => {
  if (isInstalled.value) return 'Launch StreamVault from your home screen, app drawer, Start menu, or Applications folder.'
  if (isInstallable.value) return 'Review the value, then use Install App to open the browser install confirmation.'
  if (!pwaCriteria.value.allCriteriaMet) return 'This browser session is missing one or more install prerequisites, so the native prompt may not appear.'
  return 'If your browser does not show an install prompt, follow the platform steps below.'
})

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

const enableNotificationsLabel = computed(() => {
  if (isEnablingNotifications.value) return 'Enabling...'
  if (notificationPermission.value === 'default' && !showPushPrimer.value) return 'Review first'
  if (notificationPermission.value === 'default') return 'Allow notifications'
  return 'Enable Notifications'
})

const installApp = async () => {
  try {
    isInstallingApp.value = true
    const result = await installPWA()

    if (result === 'accepted') {
      showStatus('App installation accepted', 'success')
      showInstallGuide.value = false
    } else if (result === 'dismissed') {
      showStatus('Install prompt dismissed. The setup guide stays available.', 'info')
      showInstallGuide.value = true
    } else if (result === 'installed') {
      showStatus('StreamVault is already installed', 'success')
    } else if (result === 'unavailable') {
      showStatus('Native install prompt is unavailable. Use the setup guide.', 'info')
      showInstallGuide.value = true
    } else {
      showStatus('App installation failed', 'error')
      showInstallGuide.value = true
    }
  } catch (error) {
    console.error('App installation failed:', error)
    showStatus('App installation failed', 'error')
  } finally {
    isInstallingApp.value = false
  }
}

const handleNotificationPrimaryAction = async () => {
  if (notificationPermission.value === 'default' && !showPushPrimer.value) {
    showPushPrimer.value = true
    showStatus('Review notification details before allowing browser permission', 'info')
    return
  }

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

.pwa-flow-card,
.pwa-guide-card,
.pwa-primer-card,
.pwa-primer-details {
  margin: v.$spacing-3 0;
  padding: v.$spacing-4;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  background: var(--glass-bg-subtle);
}

.pwa-flow-card {
  display: flex;
  gap: v.$spacing-3;
  align-items: flex-start;

  h5 {
    margin: 0 0 v.$spacing-1;
    color: var(--text-primary);
    font-size: v.$text-base;
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: v.$text-sm;
    line-height: 1.5;
  }
}

.pwa-flow-card__step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  border-radius: var(--radius-full);
  background: var(--primary-color);
  color: white;
  font-weight: v.$font-bold;
}

.pwa-guide-card,
.pwa-primer-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: v.$spacing-3;

  strong {
    display: block;
    margin-bottom: v.$spacing-1;
    color: var(--text-primary);
  }

  p {
    margin: 0;
    color: var(--text-secondary);
    font-size: v.$text-sm;
    line-height: 1.5;
  }

  .btn {
    min-height: 44px;
    flex-shrink: 0;
  }
}

.pwa-primer-details {
  ul {
    margin: 0;
    padding-left: v.$spacing-5;
    color: var(--text-secondary);
    font-size: v.$text-sm;
    line-height: 1.6;
  }
}

.pwa-guide-note {
  margin: v.$spacing-3 0 0;
  color: var(--warning-color);
  font-size: v.$text-sm;
  line-height: 1.5;
}

.pwa-permission-denied {
  margin-top: v.$spacing-2;
}

.pwa-error-message {
  color: var(--error-color);
}

@include m.respond-below('md') {
  .pwa-flow-card,
  .pwa-guide-card,
  .pwa-primer-card {
    flex-direction: column;
    align-items: stretch;
  }

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
