<template>
  <template v-if="showShell">
    <header class="app-header glass-header">
      <div class="header-content">
        <span class="app-logo" aria-label="StreamVault">StreamVault</span>

        <div class="header-actions" aria-label="Global utilities">
          <div class="activity-utilities" aria-label="Activity utilities">
            <BackgroundQueueMonitor />

            <button
              ref="notificationBellRef"
              class="glass-btn-icon header-utility-btn"
              :class="{ 'has-badge': unreadCount > 0 }"
              :aria-label="notificationButtonLabel"
              aria-haspopup="dialog"
              :aria-expanded="showNotifications"
              aria-controls="notification-panel"
              :title="notificationButtonLabel"
              @click.stop="toggleNotifications"
            >
              <svg>
                <use href="#icon-bell" />
              </svg>
              <span class="utility-label">Notifications</span>
              <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
            </button>
          </div>

          <div class="session-utilities" aria-label="Display and session utilities">
            <ThemeToggle />

            <button class="glass-btn-danger header-logout-btn" aria-label="Logout" @click="logout">
              <svg><use href="#icon-log-out" /></svg>
              <span class="logout-text">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </header>

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

    <Teleport to="body">
      <Transition name="fade">
        <div v-if="showNotifications" class="glass-popup-backdrop" aria-hidden="true" @click="closeNotificationPanel"></div>
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
          @keydown.esc="handleNotificationPanelEscape"
          @keydown.tab="handlePanelTab"
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
              <button class="glass-btn-icon" aria-label="Close notifications" @click="closeNotificationPanel">
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
    <slot />
  </NavigationWrapper>

  <slot v-else />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuth } from '@/composables/useAuth'
import { usePWA } from '@/composables/usePWA'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotificationStore } from '@/stores/notifications'
import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import NavigationWrapper from '@/components/navigation/NavigationWrapper.vue'

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
const showConnectivityBanner = computed(() => {
  if (!isOnline.value) return true
  return connectionStatus.value === 'reconnecting' ||
    connectionStatus.value === 'failed' ||
    connectionStatus.value === 'error' ||
    connectionStatus.value === 'auth_failed'
})
const connectivityTone = computed(() => {
  if (!isOnline.value || connectionStatus.value === 'auth_failed') return 'danger'
  if (connectionStatus.value === 'reconnecting') return 'warning'
  return 'info'
})
const connectivityIcon = computed(() => {
  if (!isOnline.value || connectionStatus.value === 'auth_failed') return '#icon-alert-triangle'
  if (connectionStatus.value === 'reconnecting') return '#icon-refresh-cw'
  return '#icon-info'
})
const connectivityTitle = computed(() => {
  if (!isOnline.value) return 'You are offline'
  if (connectionStatus.value === 'reconnecting') return 'Reconnecting live updates'
  if (connectionStatus.value === 'auth_failed') return 'Session needs attention'
  return 'Live updates paused'
})
const connectivityDescription = computed(() => {
  if (!isOnline.value) return 'StreamVault will retry when your device is back online.'
  if (connectionStatus.value === 'reconnecting') {
    return `Attempt ${reconnectAttempt.value} of ${maxReconnectAttempts} to restore live events.`
  }
  if (connectionStatus.value === 'auth_failed') return 'Sign in again to resume notifications and realtime status.'
  return 'Tap reconnect to retry now without refreshing the page.'
})
const canReconnectNow = computed(() => {
  return isOnline.value && (
    connectionStatus.value === 'failed' ||
    connectionStatus.value === 'error' ||
    connectionStatus.value === 'disconnected'
  )
})
const showNotifications = ref(false)
const notificationBellRef = ref<HTMLElement | null>(null)
const notificationPanelRef = ref<HTMLElement | null>(null)

async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

function setNotificationPanelOpen(open: boolean, restoreFocus = true) {
  showNotifications.value = open
  document.body.style.overflow = open ? 'hidden' : ''

  if (open) {
    nextTick(() => notificationPanelRef.value?.focus?.())
  } else if (restoreFocus) {
    notificationBellRef.value?.focus?.()
  }
}

function toggleNotifications() {
  setNotificationPanelOpen(!showNotifications.value)
}

async function clearAllNotifications() {
  await notificationStore.clearAll()
  closeNotificationPanel()
}

function markAsRead() {
  notificationStore.markAllRead()
}

function closeNotificationPanel() {
  if (showNotifications.value) {
    setNotificationPanelOpen(false)
  }
}

function handleNotificationPanelEscape(event: KeyboardEvent) {
  if (!showNotifications.value || event.key !== 'Escape') return

  event.preventDefault()
  event.stopPropagation()
  closeNotificationPanel()
}

function handlePanelTab(event: KeyboardEvent) {
  if (!showNotifications.value || event.key !== 'Tab') return

  const panel = notificationPanelRef.value
  if (!panel) return

  const focusable = Array.from(
    panel.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  )

  if (!focusable.length) {
    event.preventDefault()
    panel.focus()
    return
  }

  const activeElement = document.activeElement as HTMLElement | null
  const activeIndex = activeElement ? focusable.indexOf(activeElement) : -1
  const fallbackIndex = event.shiftKey ? focusable.length - 1 : 0
  const nextIndex = activeIndex === -1
    ? fallbackIndex
    : (activeIndex + (event.shiftKey ? -1 : 1) + focusable.length) % focusable.length

  event.preventDefault()
  focusable[nextIndex]?.focus()
}

function handleNotificationPanelKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    handleNotificationPanelEscape(event)
  } else if (event.key === 'Tab') {
    handlePanelTab(event)
  }
}

function handleClickOutside(event: MouseEvent) {
  if (!showNotifications.value) return

  const bell = notificationBellRef.value
  const panel = notificationPanelRef.value

  if (bell && bell.contains(event.target as Node)) return
  if (panel && panel.contains(event.target as Node)) return

  closeNotificationPanel()
}

watch(() => props.showShell, (showShell) => {
  if (!showShell) {
    closeNotificationPanel()
  }
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleNotificationPanelKeydown, true)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleNotificationPanelKeydown, true)
  if (showNotifications.value) {
    document.body.style.overflow = ''
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
  background: var(--glass-bg-strong);
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
  border-bottom: 1px solid var(--glass-border);
  box-shadow: var(--glass-shadow-sm);

  @supports not (backdrop-filter: blur(1px)) {
    background: var(--glass-bg-solid);
  }
}

.app-header .header-content {
  display: flex;
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
  font-size: var(--text-base);
  font-weight: v.$font-bold;
  color: var(--text-primary);
  line-height: 1;
  user-select: none;
  white-space: nowrap;

  @include m.respond-to('md') {
    font-size: var(--text-lg);
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  min-width: 0;
  padding: 4px;
  border-radius: calc(var(--radius-full) + 4px);
  background: rgba(255, 255, 255, 0.04);

  @include m.respond-to('md') {
    gap: var(--spacing-2);
  }

  :deep(.theme-toggle),
  :deep(.icon-btn),
  :deep(.glass-btn-icon),
  .header-utility-btn,
  .header-logout-btn {
    min-width: 44px !important;
    min-height: 44px !important;
  }
}

.activity-utilities,
.session-utilities {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: 2px;
  gap: 2px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
}

.activity-utilities {
  box-shadow: inset 0 0 0 1px var(--glass-highlight);
}

.session-utilities {
  border-color: transparent;
  background: transparent;
}

.header-utility-btn {
  gap: var(--spacing-2);
  padding: var(--spacing-2) !important;

  .badge {
    display: inline-grid;
    place-items: center;
    top: 1px;
    right: 1px;
    line-height: 1;
  }

  .utility-label {
    display: none;
    font-size: v.$text-sm;
    font-weight: v.$font-medium;
    line-height: 1;
  }

  @include m.respond-to('lg') {
    padding: var(--spacing-2) var(--spacing-3) !important;

    .utility-label {
      display: inline;
    }
  }
}

.header-logout-btn {
  padding: var(--spacing-2) !important;
  font-size: v.$text-sm;
  background: transparent;
  color: var(--text-secondary);
  border-color: transparent;

  &:hover {
    background: rgba(239, 68, 68, 0.14);
    color: var(--danger-400);
    border-color: rgba(239, 68, 68, 0.28);
  }

  .logout-text {
    display: none;

    @include m.respond-to('xl') {
      display: inline;
    }
  }
}

.glass-btn-icon.has-badge svg {
  animation: bell-shake 1s cubic-bezier(.36,.07,.19,.97) both;
  transform-origin: top center;
  color: var(--primary-color);
}

@keyframes bell-shake {
  0% { transform: rotate(0); }
  15% { transform: rotate(5deg); }
  30% { transform: rotate(-5deg); }
  45% { transform: rotate(4deg); }
  60% { transform: rotate(-4deg); }
  75% { transform: rotate(2deg); }
  85% { transform: rotate(-2deg); }
  92% { transform: rotate(1deg); }
  100% { transform: rotate(0); }
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
      min-width: 40px;
      min-height: 40px;
    }
  }

  .mark-read-btn,
  .clear-all-btn {
    min-height: 40px;
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
  position: fixed;
  top: calc(var(--app-header-height, 56px) + env(safe-area-inset-top, 0px) + var(--spacing-2));
  left: max(var(--spacing-2), env(safe-area-inset-left, 0px));
  right: max(var(--spacing-2), env(safe-area-inset-right, 0px));
  z-index: 1090;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--glass-border-hover);
  border-radius: var(--radius-xl);
  background: var(--glass-bg-strong);
  color: var(--text-primary);
  box-shadow: var(--glass-shadow-md);
  backdrop-filter: blur(var(--glass-blur-lg));
  -webkit-backdrop-filter: blur(var(--glass-blur-lg));
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
  .glass-btn-icon.has-badge svg,
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
    gap: var(--spacing-2);
  }

  .header-actions {
    gap: 2px;
    padding: 0;
  }

  .app-logo {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .activity-utilities,
  .session-utilities {
    padding: 1px;
  }
}
</style>
