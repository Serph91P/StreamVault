<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import NotificationFilters from '@/components/notifications/NotificationFilters.vue'
import NotificationItem from '@/components/notifications/NotificationItem.vue'
import NotificationState from '@/components/notifications/NotificationState.vue'
import { useNotificationStore, type NotificationFilter } from '@/stores/notifications'
import type { StoredNotification } from '@/services/notificationStorage'
import { normalizeNotificationTargetUrl } from '@/types/events'

const emit = defineEmits<{
  (e: 'notifications-read'): void
  (e: 'close-panel'): void
  (e: 'clear-all'): void
  (e: 'close'): void
}>()

const notificationStore = useNotificationStore()
const router = useRouter()
const isLoading = ref(false)
const errorMessage = ref('')

const notifications = computed(() => notificationStore.filteredNotifications)
const totalCount = computed(() => notificationStore.totalCount)
const unreadCount = computed(() => notificationStore.unreadCount)
const groupedNotifications = computed(() => notificationStore.groupedNotifications)

const activeFilter = computed<NotificationFilter>({
  get: () => notificationStore.filter,
  set: (value) => notificationStore.setFilter(value)
})

const severityCounts = computed(() => notificationStore.severityCounts)
const sourceOptions = computed(() => notificationStore.sourceOptions)
const typeOptions = computed(() => notificationStore.typeOptions)

const subtitle = computed(() => {
  if (unreadCount.value > 0) {
    return `${unreadCount.value} unread of ${totalCount.value} notification${totalCount.value !== 1 ? 's' : ''}`
  }
  return `${totalCount.value} notification${totalCount.value !== 1 ? 's' : ''} in history`
})

async function openNotificationTarget(notification: StoredNotification): Promise<void> {
  if (!notification.target_url) {
    return
  }

  notificationStore.markRead(notification.id)

  try {
    const target = normalizeNotificationTargetUrl(notification.target_url)
    if (target.startsWith(window.location.origin)) {
      const targetUrl = new URL(target)
      await router.push(targetUrl.pathname + targetUrl.search + targetUrl.hash)
    } else if (target.startsWith('/')) {
      await router.push(target)
    } else {
      window.open(target, '_blank', 'noopener,noreferrer')
    }
    emit('close-panel')
  } catch (error) {
    errorMessage.value = 'The notification target could not be opened.'
    console.error('NotificationFeed: Failed to open notification target:', error)
  }
}

function toggleRead(notification: StoredNotification): void {
  if (notification.read) {
    notificationStore.markUnread(notification.id)
  } else {
    notificationStore.markRead(notification.id)
  }
}

function removeNotification(id: string): void {
  notificationStore.remove(id)
}

function markAllRead(event?: Event): void {
  event?.preventDefault()
  event?.stopPropagation()
  notificationStore.markAllRead()
  emit('notifications-read')
}

async function clearAllNotifications(event?: Event): Promise<void> {
  event?.preventDefault()
  event?.stopPropagation()
  await notificationStore.clearAll()
  emit('clear-all')
  emit('close-panel')
}

async function refreshNotifications(): Promise<void> {
  isLoading.value = true
  errorMessage.value = ''

  try {
    notificationStore.load()
    await notificationStore.syncBackendState()
  } catch (error) {
    errorMessage.value = 'Notifications could not be refreshed. Existing local items are still available.'
    console.error('NotificationFeed: Failed to refresh notifications:', error)
  } finally {
    isLoading.value = false
  }
}

function closeFeed(): void {
  emit('close')
}

onMounted(() => {
  refreshNotifications()
})
</script>

<template>
  <section class="notification-feed" aria-label="Notification Center">
    <header class="feed-header">
      <div class="header-content">
        <div class="header-icon" aria-hidden="true">
          <svg class="bell-svg"><use href="#icon-bell" /></svg>
        </div>
        <div class="header-text">
          <p class="eyebrow">Notification Center</p>
          <h2 class="section-title">Stay on top of StreamVault</h2>
          <p class="section-subtitle">{{ subtitle }}</p>
          <p class="channel-explainer">
            In-app events arrive live over WebSocket. External delivery still uses your configured Apprise and push targets.
          </p>
        </div>
      </div>
      <div class="header-actions">
        <button
          v-if="unreadCount > 0"
          type="button"
          class="header-action mark-read-action"
          aria-label="Mark all notifications read"
          @click="markAllRead"
        >
          Mark all read
        </button>
        <button
          v-if="totalCount > 0"
          type="button"
          class="header-action clear-action"
          aria-label="Clear all notifications"
          @click="clearAllNotifications"
        >
          Clear all
        </button>
        <button
          type="button"
          class="header-action icon-action"
          aria-label="Close notifications"
          @click="closeFeed"
        >
          <svg class="close-svg"><use href="#icon-x" /></svg>
        </button>
      </div>
    </header>

    <NotificationFilters
      v-if="totalCount > 0"
      v-model="activeFilter"
      :total-count="totalCount"
      :unread-count="unreadCount"
      :severity-counts="severityCounts"
      :source-options="sourceOptions"
      :type-options="typeOptions"
    />

    <NotificationState
      v-if="isLoading"
      state="loading"
      title="Loading notifications"
      message="Fetching your latest stream, recording and system events."
    />
    <NotificationState
      v-else-if="errorMessage"
      state="error"
      title="Notification Center needs attention"
      :message="errorMessage"
      action-label="Retry"
      @action="refreshNotifications"
    />
    <NotificationState
      v-else-if="totalCount === 0"
      state="empty"
      title="All caught up"
      message="Important stream, recording, queue and system events will appear here."
    />
    <NotificationState
      v-else-if="notifications.length === 0"
      state="empty"
      title="No matches"
      message="Try another filter or switch back to all notifications."
    />

    <div v-else class="notification-groups">
      <section
        v-for="group in groupedNotifications"
        :key="group.key"
        class="notification-group"
        :aria-labelledby="`notification-group-${group.key}`"
      >
        <header class="notification-group-header">
          <h3 :id="`notification-group-${group.key}`">{{ group.title }}</h3>
          <span>
            {{ group.notifications.length }} item{{ group.notifications.length !== 1 ? 's' : '' }}
            <template v-if="group.unreadCount > 0">, {{ group.unreadCount }} unread</template>
          </span>
        </header>
        <TransitionGroup name="notification" tag="div" class="notification-list">
          <NotificationItem
            v-for="notification in group.notifications"
            :key="notification.id"
            :notification="notification"
            @open="openNotificationTarget"
            @remove="removeNotification"
            @toggle-read="toggleRead"
          />
        </TransitionGroup>
      </section>
    </div>
  </section>
</template>

<style scoped lang="scss">
@use '@/styles/mixins' as m;

.notification-feed {
  position: static;
  inset: auto;
  z-index: auto;
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
  max-width: none;
  min-height: 0;
  overflow: hidden;
  pointer-events: auto;
}

.feed-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-4);
  padding: var(--spacing-5);
  border-bottom: 1px solid var(--glass-border);
  background: var(--glass-bg-medium);
}

.header-content {
  display: flex;
  gap: var(--spacing-3);
  min-width: 0;
}

.header-icon {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid rgba(145, 71, 255, 0.5);
  border-radius: var(--radius-full);
  background: rgba(145, 71, 255, 0.16);
  color: var(--primary-color);
}

.bell-svg,
.close-svg {
  width: 1.15rem;
  height: 1.15rem;
  stroke: currentColor;
  fill: none;
}

.header-text {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 var(--spacing-1);
  color: var(--primary-color);
  font-size: var(--text-xs);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.section-title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
  font-weight: 800;
  line-height: 1.2;
}

.section-subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.channel-explainer {
  max-width: 28rem;
  margin: var(--spacing-2) 0 0;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
  line-height: 1.45;
}

.header-actions {
  display: inline-flex;
  flex: 0 0 auto;
  gap: var(--spacing-2);
}

.header-action {
  min-height: 44px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: var(--glass-bg-subtle);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 700;
  cursor: pointer;
}

.header-action:hover,
.header-action:focus-visible {
  border-color: var(--primary-color);
  color: var(--text-primary);
  outline: none;
}

.clear-action {
  padding: 0 var(--spacing-3);
}

.icon-action {
  display: grid;
  place-items: center;
  width: 44px;
  padding: 0;
}

.notification-groups {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  max-height: calc(76vh - 150px);
  padding: var(--spacing-1) var(--spacing-1) var(--spacing-3);
}

.notification-group + .notification-group {
  margin-top: var(--spacing-2);
}

.notification-group-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-5) var(--spacing-2);
  background: linear-gradient(180deg, var(--glass-bg-strong), rgba(15, 23, 42, 0.72));
  color: var(--text-secondary);
}

.notification-group-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 800;
}

.notification-group-header span {
  flex: 0 0 auto;
  font-size: var(--text-xs);
}

.notification-list {
  padding: 0 var(--spacing-1) var(--spacing-2);
}

.notification-groups::-webkit-scrollbar {
  width: 6px;
}

.notification-groups::-webkit-scrollbar-track {
  background: transparent;
}

.notification-groups::-webkit-scrollbar-thumb {
  border-radius: var(--radius-full);
  background-color: rgba(255, 255, 255, 0.14);
}

.notification-enter-active,
.notification-leave-active {
  transition: opacity var(--duration-200) var(--ease-out), transform var(--duration-200) var(--ease-out);
}

.notification-enter-from {
  opacity: 0;
  transform: translateY(-0.75rem);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(1rem);
}

.notification-move {
  transition: transform var(--duration-200) var(--ease-out);
}

@include m.respond-below('md') {
  .notification-feed {
    max-height: calc(100dvh - var(--safe-area-inset-top, 0px));
    overflow: visible;
  }

  .notification-groups {
    max-height: none;
  }

  .feed-header {
    align-items: flex-start;
    padding: var(--spacing-4);
  }

  .section-title {
    font-size: var(--text-base);
  }

  .header-actions {
    flex-direction: column-reverse;
    align-items: flex-end;
  }

  .clear-action {
    min-height: 44px;
    padding: 0 var(--spacing-2);
    font-size: var(--text-xs);
  }

  .notification-groups,
  .notification-list {
    padding-inline: var(--spacing-2);
  }
}
</style>
