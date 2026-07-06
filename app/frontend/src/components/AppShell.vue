<template>
  <template v-if="showShell">
    <header class="app-header glass-header">
      <div class="header-content">
        <span class="app-logo" aria-label="StreamVault">StreamVault</span>

        <div class="header-actions">
          <BackgroundQueueMonitor />

          <button
            ref="notificationBellRef"
            class="glass-btn-icon"
            :class="{ 'has-badge': unreadCount > 0 }"
            aria-label="Notifications"
            aria-haspopup="dialog"
            :aria-expanded="showNotifications"
            aria-controls="notification-panel"
            @click.stop="toggleNotifications"
          >
            <svg>
              <use href="#icon-bell" />
            </svg>
            <span v-if="unreadCount > 0" class="badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>

          <ThemeToggle />

          <button class="glass-btn-danger header-logout-btn" aria-label="Logout" @click="logout">
            <svg><use href="#icon-log-out" /></svg>
            <span class="logout-text">Logout</span>
          </button>
        </div>
      </div>
    </header>

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
          @keydown.esc="closeNotificationPanel"
          @keydown.tab="handlePanelTab"
        >
          <div class="glass-popup-header">
            <h3 id="notification-panel-title">Notifications</h3>
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
const notificationStore = useNotificationStore()
const unreadCount = computed(() => notificationStore.unreadCount)
const notificationCount = computed(() => notificationStore.totalCount)
const showNotifications = ref(false)
const notificationBellRef = ref<HTMLElement | null>(null)
const notificationPanelRef = ref<HTMLElement | null>(null)

async function logout() {
  if (confirm('Are you sure you want to logout?')) {
    await authLogout()
  }
}

function toggleNotifications() {
  showNotifications.value = !showNotifications.value
  document.body.style.overflow = showNotifications.value ? 'hidden' : ''

  if (showNotifications.value) {
    nextTick(() => notificationPanelRef.value?.focus?.())
  } else {
    notificationBellRef.value?.focus?.()
  }
}

async function clearAllNotifications() {
  await notificationStore.clearAll()
}

function markAsRead() {
  notificationStore.markAllRead()
}

function closeNotificationPanel() {
  if (showNotifications.value) {
    showNotifications.value = false
    document.body.style.overflow = ''
    notificationBellRef.value?.focus?.()
  }
}

function handlePanelTab(event: KeyboardEvent) {
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

  const first = focusable[0]
  const last = focusable[focusable.length - 1]

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
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
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
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
  height: 64px;
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
  height: 100%;
  padding: 0 var(--spacing-4);

  @include m.respond-to('md') {
    padding: 0 var(--spacing-6);
  }
}

.app-logo {
  font-size: var(--text-lg);
  font-weight: v.$font-bold;
  color: var(--primary-color);
  line-height: 1;
  user-select: none;

  @include m.respond-to('md') {
    font-size: var(--text-xl);
  }
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);

  @include m.respond-to('md') {
    gap: var(--spacing-2);
  }
}

.header-logout-btn {
  padding: var(--spacing-2) var(--spacing-3) !important;
  min-height: 36px !important;
  font-size: v.$text-sm;

  .logout-text {
    display: none;

    @include m.respond-to('md') {
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
  :deep(.notification-feed .feed-header) {
    display: none !important;
  }

  .notification-header-actions {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
  }

  .clear-all-btn {
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
  .app-header .header-content {
    padding: 0 var(--spacing-3);
  }
}
</style>
