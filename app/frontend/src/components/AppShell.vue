<template>
  <template v-if="showShell">
    <header class="app-header">
      <div class="header-content">
        <router-link to="/" class="app-logo" aria-label="StreamVault - Meine Kanäle">StreamVault</router-link>

        <div class="shell-utilities" aria-label="Global utilities">
          <div class="activity-utilities" aria-label="Activity utilities">
            <BackgroundQueueMonitor />

            <button
              ref="notificationBellRef"
              type="button"
              class="header-utility-btn"
              :class="{ 'has-badge': unreadCount > 0 }"
              :aria-label="notificationButtonLabel"
              aria-haspopup="dialog"
              :aria-expanded="showNotifications"
              aria-controls="notification-panel"
              :title="notificationButtonLabel"
              @click.stop="toggleNotifications"
            >
              <svg aria-hidden="true">
                <use href="#icon-bell" />
              </svg>
              <span class="utility-label">Notifications</span>
              <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </button>
          </div>

          <div class="session-utilities" aria-label="Display and session utilities">
            <ThemeToggle />

            <button type="button" class="header-utility-btn header-logout-btn" aria-label="Logout" @click="logout">
              <svg aria-hidden="true"><use href="#icon-log-out" /></svg>
              <span class="logout-text">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </header>


    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showNotifications" class="glass-popup-backdrop" aria-hidden="true" @click="closeNotificationPanel()"></div>
      </Transition>
      <Transition name="slide-up">
        <div
          v-if="showNotifications"
          id="notification-panel"
          ref="notificationPanelRef"
          class="glass-popup-panel notification-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="notification-panel-title"
          tabindex="-1"
        >
          <div class="glass-popup-header notification-panel-header">
            <div class="notification-title-stack">
              <h3 id="notification-panel-title">Notifications</h3>
              <p class="notification-panel-count">{{ notificationPanelSubtitle }}</p>
            </div>
            <div class="notification-header-actions">
              <button
                v-if="unreadCount > 0"
                class="glass-btn-text mark-read-btn"
                aria-label="Mark all notifications read"
                title="Mark all notifications read"
                @click="markAsRead"
              >
                Mark all read
              </button>
              <button
                v-if="notificationCount > 0"
                class="glass-btn-text clear-all-btn"
                aria-label="Clear all notifications"
                title="Clear all notifications"
                @click="clearAllNotifications"
              >
                Clear all
              </button>
              <button class="glass-btn-icon" aria-label="Close notifications" @click="closeNotificationPanel()">
                <svg><use href="#icon-x" /></svg>
              </button>
            </div>
          </div>
          <NotificationFeed
            @notifications-read="markAsRead"
            @close-panel="closeNotificationPanel"
            @clear-all="clearAllNotifications"
            @close="closeNotificationPanel"
          />
        </div>
      </Transition>
    </Teleport>
  </template>

  <NavigationWrapper v-if="showShell">
    <div
      v-if="showConnectivityBanner"
      class="connectivity-banner"
      :class="`connectivity-banner--${connectivityTone}`"
      role="status"
      aria-live="polite"
    >
      <div class="connectivity-banner__content">
        <svg class="connectivity-banner__icon" aria-hidden="true">
          <use :href="connectivityIcon" />
        </svg>
        <div class="connectivity-banner__copy">
          <strong>{{ connectivityTitle }}</strong>
          <span>{{ connectivityDescription }}</span>
        </div>
      </div>
      <button
        v-if="canReconnectNow"
        class="connectivity-banner__action"
        type="button"
        @click="reconnectNow"
      >
        Reconnect
      </button>
    </div>
    <slot />
  </NavigationWrapper>

  <slot v-else />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { usePWA } from '@/composables/usePWA'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotificationStore } from '@/stores/notifications'
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'
import { useModal } from '@/composables/useModal'

const props = withDefaults(defineProps<{
  showShell?: boolean
}>(), {
  showShell: true
})

const { logout: authLogout } = useAuth()
const { isOnline } = usePWA()
const {
  connectionStatus,
  reconnectAttempt,
  maxReconnectAttempts,
  reconnectNow
} = useWebSocket()
const notificationStore = useNotificationStore()
const unreadCount = computed(() => notificationStore.unreadCount)
const notificationCount = computed(() => notificationStore.totalCount)
const notificationPanelSubtitle = computed(() => {
  if (unreadCount.value > 0) {
    return `${unreadCount.value} unread of ${notificationCount.value} notification${notificationCount.value !== 1 ? 's' : ''}`
  }

  if (notificationCount.value > 0) {
    return `${notificationCount.value} notification${notificationCount.value !== 1 ? 's' : ''} in history`
  }

  return 'All caught up'
})
const notificationButtonLabel = computed(() => {
  if (unreadCount.value > 0) {
    return `Open notifications, ${unreadCount.value} unread`
  }

  return 'Open notifications'
})
// A retry handshake is still reconnecting; keep its in-flow status until connected.
const connectivityStatus = computed(() =>
  connectionStatus.value === 'connecting' && reconnectAttempt.value > 0
    ? 'reconnecting'
    : connectionStatus.value
)
const showConnectivityBanner = computed(() => {
  if (!isOnline.value) return true
  return connectivityStatus.value === 'reconnecting' ||
    connectivityStatus.value === 'failed' ||
    connectivityStatus.value === 'error' ||
    connectivityStatus.value === 'auth_failed'
})
const connectivityTone = computed(() => {
  if (!isOnline.value || connectivityStatus.value === 'auth_failed') return 'danger'
  if (connectivityStatus.value === 'reconnecting') return 'warning'
  return 'info'
})
const connectivityIcon = computed(() => {
  if (!isOnline.value || connectivityStatus.value === 'auth_failed') return '#icon-alert-triangle'
  if (connectivityStatus.value === 'reconnecting') return '#icon-refresh-cw'
  return '#icon-info'
})
const connectivityTitle = computed(() => {
  if (!isOnline.value) return 'You are offline'
  if (connectivityStatus.value === 'reconnecting') return 'Reconnecting live updates'
  if (connectivityStatus.value === 'auth_failed') return 'Session needs attention'
  return 'Live updates paused'
})
const connectivityDescription = computed(() => {
  if (!isOnline.value) return 'StreamVault will retry when your device is back online.'
  if (connectivityStatus.value === 'reconnecting') {
    return `Attempt ${reconnectAttempt.value} of ${maxReconnectAttempts} to restore live events.`
  }
  if (connectivityStatus.value === 'auth_failed') return 'Sign in again to resume notifications and realtime status.'
  return 'Tap reconnect to retry now without refreshing the page.'
})
const canReconnectNow = computed(() => {
  return isOnline.value && (
    connectivityStatus.value === 'failed' ||
    connectivityStatus.value === 'error' ||
    connectivityStatus.value === 'disconnected'
  )
})
const notificationBellRef = ref<HTMLElement | null>(null)
const notificationPanelRef = ref<HTMLElement | null>(null)
const {
  isOpen: showNotifications,
  open: openNotificationPanel,
  close: closeNotificationPanel,
} = useModal(notificationPanelRef)

async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

function toggleNotifications() {
  if (showNotifications.value) closeNotificationPanel()
  else openNotificationPanel()
}

async function clearAllNotifications() {
  await notificationStore.clearAll()
  closeNotificationPanel()
}

function markAsRead() {
  notificationStore.markAllRead()
}

watch(() => props.showShell, (showShell) => {
  if (!showShell) {
    closeNotificationPanel()
  }
})
</script>

<style scoped lang="scss">
@use '@/styles/variables' as v;
@use '@/styles/mixins' as m;

.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px));
  min-height: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px));
  padding: env(safe-area-inset-top, 0px) 0 0;
  box-sizing: border-box;
  display: block;
  z-index: 1100;
  background: var(--sv-cmp-panel-background);
  border-bottom: 1px solid var(--sv-cmp-panel-border);
  box-shadow: none;
}

.app-header .header-content {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: space-between;
  height: var(--app-header-height, 56px);
  padding: 0 var(--spacing-3);
  gap: var(--spacing-3);

  @include m.respond-to('md') {
    padding: 0 var(--spacing-4);
  }
}

.app-logo {
  display: inline-flex;
  align-items: center;
  min-height: 44px;
  min-width: 0;
  font-size: var(--text-base);
  text-decoration: none;
  font-weight: v.$font-semibold;
  letter-spacing: -0.025em;
  color: var(--sv-sem-text-primary);
  line-height: 1;
  user-select: none;
  white-space: nowrap;

  @include m.respond-to('md') {
    font-size: var(--text-lg);
  }
}

.shell-utilities {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  min-width: 0;
  flex-shrink: 0;

  @include m.respond-to('md') {
    gap: var(--spacing-2);
  }

  :deep(.theme-toggle),
  :deep(.queue-status-indicator) {
    min-width: var(--sv-fdn-size-target-primary);
    min-height: var(--sv-fdn-size-target-primary);
    border: 1px solid transparent;
    border-radius: var(--sv-fdn-radius-md);
    background: transparent;
    color: var(--sv-sem-text-secondary);
    box-shadow: none;

    &:hover {
      background: var(--sv-sem-surface-raised);
      color: var(--sv-sem-text-primary);
      transform: none;
      box-shadow: none;
    }
  }

  :deep(.queue-status-indicator) {
    padding-inline: var(--spacing-3);
  }

  :deep(.queue-count) {
    color: var(--sv-sem-text-primary);
  }
}

.activity-utilities,
.session-utilities {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 2px;
}

.session-utilities {
  padding-left: var(--spacing-2);
  border-left: 1px solid var(--sv-sem-border-default);
}

.header-utility-btn {
  position: relative;
  min-width: var(--sv-fdn-size-target-primary);
  min-height: var(--sv-fdn-size-target-primary);
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  border: 1px solid transparent;
  border-radius: var(--sv-fdn-radius-md);
  background: transparent;
  color: var(--sv-sem-text-secondary);
  box-shadow: none;

  &:hover {
    background: var(--sv-sem-surface-raised);
    color: var(--sv-sem-text-primary);
    transform: none;
    box-shadow: none;
  }

  &:focus-visible {
    outline: 2px solid var(--sv-sem-action-focus);
    outline-offset: 2px;
  }

  svg {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: currentColor;
  }

  .badge {
    position: absolute;
    display: inline-grid;
    place-items: center;
    top: 3px;
    right: 2px;
    min-width: 18px;
    height: 18px;
    padding-inline: var(--spacing-1);
    background: var(--sv-sem-action-primary);
    color: var(--sv-sem-text-inverse);
    border-radius: var(--sv-fdn-radius-round);
    font-size: var(--text-xs);
    line-height: 1;
  }

  .utility-label {
    display: none;
    font-size: v.$text-sm;
    font-weight: v.$font-medium;
    line-height: 1;
  }

  @include m.respond-to('lg') {
    padding: var(--spacing-2) var(--spacing-3);

    .utility-label {
      display: inline;
    }

    .badge {
      position: static;
    }
  }
}

.header-logout-btn {
  font-size: v.$text-sm;

  &:hover {
    color: var(--sv-sem-status-danger);
  }

  .logout-text {
    display: none;

    @include m.respond-to('xl') {
      display: inline;
    }
  }
}

.notification-panel {
  width: min(440px, calc(100vw - var(--spacing-4)));
  max-height: min(76vh, 680px);

  .notification-panel-header {
    gap: var(--spacing-3);
    padding: var(--spacing-4) var(--spacing-5);
  }

  .notification-title-stack {
    min-width: 0;
  }

  .notification-panel-count {
    margin: var(--spacing-1) 0 0;
    color: var(--text-secondary);
    font-size: var(--text-xs);
    line-height: 1.3;
  }

  :deep(.notification-feed .feed-header) {
    display: none !important;
  }

  .notification-header-actions {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);

    .glass-btn-icon {
      min-width: 44px;
      min-height: 44px;
    }
  }

  .mark-read-btn,
  .clear-all-btn {
    min-height: 44px;
    background: transparent;
    border: 1px solid var(--glass-border-hover);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background var(--duration-150) var(--ease-out),
                color var(--duration-150) var(--ease-out),
                border-color var(--duration-150) var(--ease-out);

    &:hover {
      background: var(--glass-bg-subtle);
      color: var(--text-primary);
      border-color: var(--text-secondary);
    }

    &:active {
      transform: translateY(1px);
    }
  }

  @include m.respond-below('lg') {
    .notification-feed {
      flex: 1;
      overflow-y: auto;
    }
  }

  @include m.respond-below('md') {
    max-height: 100dvh;
    height: 100dvh;
    padding-bottom: env(safe-area-inset-bottom);

    .notification-panel-header {
      align-items: flex-start;
      padding: max(var(--spacing-4), env(safe-area-inset-top)) var(--spacing-4) var(--spacing-3);
    }

    .notification-header-actions {
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .mark-read-btn,
    .clear-all-btn {
      padding-inline: var(--spacing-2);
      font-size: var(--text-xs);
    }
  }
}

.connectivity-banner {
  // The shared main already reserves the fixed header. Natural flow reserves
  // this banner's real wrapped height, including its interactive retry action.
  margin: var(--spacing-2) max(var(--spacing-2), env(safe-area-inset-right, 0px)) var(--spacing-2) max(var(--spacing-2), env(safe-area-inset-left, 0px));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--sv-sem-border-default);
  border-radius: var(--sv-fdn-radius-md);
  background: var(--sv-sem-surface-panel);
  color: var(--sv-sem-text-primary);

}

.connectivity-banner--danger {
  border-color: rgba(239, 68, 68, 0.38);
}

.connectivity-banner--warning {
  border-color: rgba(245, 158, 11, 0.42);
}

.connectivity-banner--info {
  border-color: rgba(59, 130, 246, 0.36);
}

.connectivity-banner__content {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  min-width: 0;
}

.connectivity-banner__icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  color: var(--primary-color);
}

.connectivity-banner__copy {
  display: grid;
  gap: 2px;
  min-width: 0;

  strong {
    font-size: var(--text-sm);
    line-height: 1.2;
  }

  span {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    line-height: 1.35;
  }
}

.connectivity-banner__action {
  min-height: 44px;
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px solid var(--glass-border-hover);
  border-radius: var(--radius-md);
  background: var(--glass-bg-subtle);
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity v.$duration-200 v.$ease-out;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: transform v.$duration-300 v.$ease-out, opacity v.$duration-200 v.$ease-out;
}
.slide-up-enter-from {
  transform: translateY(20px);
  opacity: 0;
}
.slide-up-leave-to {
  transform: translateY(10px);
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .fade-enter-active,
  .fade-leave-active,
  .slide-up-enter-active,
  .slide-up-leave-active {
    animation: none;
    transition: none;
  }
}

@include m.respond-below('md') {
  .connectivity-banner {
    align-items: stretch;
    flex-direction: column;
    gap: var(--spacing-2);
    max-height: calc(100dvh - var(--app-header-height, 56px) - 88px - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px));
    overflow-y: auto;
  }

  .connectivity-banner__action {
    width: 100%;
  }

  .app-header .header-content {
    padding: 0 var(--spacing-2);
    gap: 0;
  }

  .shell-utilities {
    gap: 0;

    :deep(.queue-info) { display: none; }
    :deep(.queue-status-indicator) { padding-inline: var(--spacing-2); }
  }

  .app-logo {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .session-utilities {
    padding-left: 0;
    border-left: 0;
  }

  .activity-utilities,
  .session-utilities {
    gap: 0;
  }
}
</style>
