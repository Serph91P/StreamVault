<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge, { type StatusBadgeTone } from '@/components/base/StatusBadge.vue'
import { useCategoryImages } from '@/composables/useCategoryImages'
import type { StoredNotification } from '@/services/notificationStorage'

interface Props {
  notification: StoredNotification
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'open', notification: StoredNotification): void
  (e: 'remove', id: string): void
  (e: 'toggle-read', notification: StoredNotification): void
}>()

const { getCategoryImage } = useCategoryImages()

const categoryName = computed(() => {
  return props.notification.data?.game_name || props.notification.data?.category_name || ''
})

const categoryImage = computed(() => {
  return categoryName.value ? getCategoryImage(String(categoryName.value)) : ''
})

const statusTone = computed(() => getNotificationTone(props.notification))
const hasTarget = computed(() => Boolean(props.notification.target_url))
const displayTitle = computed(() => {
  if (isStreamUpdateNotification(props.notification)) {
    return firstNotificationString(
      props.notification.streamer_name,
      props.notification.streamer_username,
      props.notification.data?.streamer_name,
      props.notification.data?.username
    ) || props.notification.title
  }

  return props.notification.title
})
const showSeverityBadge = computed(() => {
  return !(isStreamUpdateNotification(props.notification) && props.notification.severity === 'info')
})
const typeLabel = computed(() => props.notification.type.replaceAll('.', ' '))

function firstNotificationString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value
    }
  }
}

function isStreamUpdateNotification(notification: StoredNotification): boolean {
  return notification.type === 'channel.update' || notification.type === 'stream.update'
}

function formatTime(timestamp: string): string {
  const now = new Date()
  const time = new Date(timestamp)
  const diff = now.getTime() - time.getTime()

  if (!Number.isFinite(diff)) return 'Unknown time'
  if (diff < 60 * 1000) return 'Just now'
  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`
  }
  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours} hour${hours !== 1 ? 's' : ''} ago`
  }
  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    return `${days} day${days !== 1 ? 's' : ''} ago`
  }
  return time.toLocaleDateString()
}

function getNotificationTone(notification: StoredNotification): StatusBadgeTone {
  if (notification.severity === 'critical' || notification.severity === 'error') return 'danger'
  if (notification.severity === 'warning') return 'warning'
  if (notification.severity === 'success') return 'success'

  switch (notification.type) {
    case 'stream.online':
      return 'live'
    case 'stream.offline':
      return 'offline'
    case 'channel.update':
    case 'stream.update':
      return 'info'
    case 'recording.started':
      return 'recording'
    case 'recording.completed':
    case 'recording.finished':
    case 'recording.available':
      return 'success'
    case 'recording.failed':
      return 'danger'
    case 'test':
      return 'info'
    default:
      return 'info'
  }
}

function iconFor(notification: StoredNotification): string {
  if (notification.severity === 'critical' || notification.severity === 'error') return '#icon-alert-circle'
  if (notification.severity === 'warning') return '#icon-alert-triangle'
  if (notification.severity === 'success') return '#icon-check-circle'

  switch (notification.type) {
    case 'stream.online':
      return '#icon-radio'
    case 'stream.offline':
      return '#icon-circle'
    case 'channel.update':
    case 'stream.update':
      return '#icon-edit'
    case 'recording.started':
      return '#icon-video'
    case 'recording.completed':
    case 'recording.finished':
    case 'recording.available':
      return '#icon-check-circle'
    case 'recording.failed':
      return '#icon-alert-circle'
    case 'test':
      return '#icon-info'
    default:
      return '#icon-info'
  }
}

function openNotification() {
  if (hasTarget.value) {
    emit('open', props.notification)
  }
}
</script>

<template>
  <article
    class="notification-item"
    :class="[statusTone, { unread: !notification.read, 'has-target': hasTarget }]"
    :aria-label="`${displayTitle}. ${notification.body}`"
    :tabindex="hasTarget ? 0 : undefined"
    @click="openNotification"
    @keydown.enter="openNotification"
    @keydown.space.prevent="openNotification"
  >
    <div class="notification-accent" aria-hidden="true"></div>

    <div class="notification-icon" :class="statusTone" aria-hidden="true">
      <svg class="notif-svg"><use :href="iconFor(notification)" /></svg>
    </div>

    <div class="notification-content">
      <div class="notification-title-row">
        <div class="title-stack">
          <span v-if="!notification.read" class="unread-dot" aria-label="Unread notification"></span>
          <h3>{{ displayTitle }}</h3>
        </div>
        <time :datetime="notification.timestamp">{{ formatTime(notification.timestamp) }}</time>
      </div>

      <p class="notification-message">{{ notification.body }}</p>

      <div class="notification-meta" aria-label="Notification details">
        <StatusBadge
          v-if="showSeverityBadge"
          class="notification-severity-badge"
          :tone="statusTone"
          size="sm"
          :aria-label="`Notification severity: ${notification.severity}`"
        >
          {{ notification.severity }}
        </StatusBadge>
        <span class="meta-pill">{{ typeLabel }}</span>
        <span v-if="categoryName" class="meta-pill category-tag">
          <span class="category-image-small" aria-hidden="true">
            <img
              v-if="categoryImage && !categoryImage.startsWith('icon:')"
              :src="categoryImage"
              :alt="String(categoryName)"
              loading="lazy"
            />
            <i v-else-if="categoryImage" :class="categoryImage.replace('icon:', '')" class="category-icon"></i>
          </span>
          {{ categoryName }}
        </span>
      </div>
    </div>

    <div class="notification-actions">
      <button
        v-if="hasTarget"
        type="button"
        class="item-action primary"
        :aria-label="`Open notification target for ${displayTitle}`"
        @click.stop="emit('open', notification)"
      >
        Open
      </button>
      <button
        type="button"
        class="item-action"
        :aria-label="notification.read ? `Mark ${displayTitle} unread` : `Mark ${displayTitle} read`"
        @click.stop="emit('toggle-read', notification)"
      >
        {{ notification.read ? 'Unread' : 'Read' }}
      </button>
      <button
        type="button"
        class="item-action icon-only"
        :aria-label="`Dismiss ${displayTitle}`"
        @click.stop="emit('remove', notification.id)"
      >
        ×
      </button>
    </div>
  </article>
</template>

<style scoped lang="scss">
.notification-item {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: var(--spacing-3);
  align-items: flex-start;
  margin: var(--spacing-3) var(--spacing-4);
  padding: var(--spacing-4);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  background: var(--glass-bg-subtle);
  color: var(--text-primary);
  transition: transform var(--duration-200) var(--ease-out), border-color var(--duration-200) var(--ease-out), background var(--duration-200) var(--ease-out);
}

.notification-item:hover,
.notification-item:focus-visible {
  border-color: var(--glass-border-hover);
  background: var(--glass-bg-medium);
  transform: translateY(-1px);
  outline: none;
}

.notification-item.has-target {
  cursor: pointer;
}

.notification-item.unread {
  border-color: rgba(0, 180, 216, 0.4);
  background: linear-gradient(135deg, rgba(0, 180, 216, 0.1), var(--glass-bg-subtle));
}

.notification-accent {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  border-radius: var(--radius-xl) 0 0 var(--radius-xl);
  background: var(--info-color);
  opacity: 0.8;
}

.notification-item.danger .notification-accent,
.notification-item.live .notification-accent,
.notification-item.recording .notification-accent {
  background: var(--danger-color);
}

.notification-item.warning .notification-accent {
  background: var(--warning-color);
}

.notification-item.success .notification-accent {
  background: var(--success-color);
}

.notification-item.offline .notification-accent {
  background: var(--text-secondary);
}

.notification-icon {
  display: grid;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: var(--radius-full);
  background: rgba(0, 180, 216, 0.12);
  color: var(--info-color);
}

.notification-icon.danger,
.notification-icon.live,
.notification-icon.recording {
  background: rgba(244, 67, 54, 0.14);
  color: var(--danger-color);
}

.notification-icon.warning {
  background: rgba(255, 152, 0, 0.14);
  color: var(--warning-color);
}

.notification-icon.success {
  background: rgba(29, 185, 84, 0.14);
  color: var(--success-color);
}

.notification-icon.offline {
  background: rgba(148, 163, 184, 0.14);
  color: var(--text-secondary);
}

.notif-svg {
  width: 1.2rem;
  height: 1.2rem;
  stroke: currentColor;
  fill: none;
}

.notification-content {
  min-width: 0;
}

.notification-title-row {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-2);
}

.title-stack {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  min-width: 0;
}

.title-stack h3 {
  margin: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 700;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.unread-dot {
  flex: 0 0 auto;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: var(--radius-full);
  background: var(--info-color);
  box-shadow: 0 0 0 4px rgba(0, 180, 216, 0.14);
}

time {
  flex: 0 0 auto;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.notification-message {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.45;
  word-break: break-word;
}

.notification-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
  margin-top: var(--spacing-3);
}

.meta-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  max-width: 100%;
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: 1.2;
}

.dedupe {
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-image-small {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  height: 1rem;
  overflow: hidden;
  border-radius: var(--radius-sm);
}

.category-image-small img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.category-icon {
  font-size: var(--text-xs);
  color: var(--twitch-purple);
}

.notification-actions {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  align-items: flex-end;
}

.item-action {
  min-height: 44px;
  padding: 0 var(--spacing-3);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 700;
  cursor: pointer;
}

.item-action:hover,
.item-action:focus-visible {
  border-color: var(--primary-color);
  color: var(--text-primary);
  outline: none;
}

.item-action.primary {
  border-color: rgba(145, 71, 255, 0.45);
  background: rgba(145, 71, 255, 0.14);
  color: var(--text-primary);
}

.item-action.icon-only {
  width: 44px;
  padding: 0;
  font-size: var(--text-lg);
  line-height: 1;
}

@media (max-width: 767px) {
  .notification-item {
    grid-template-columns: auto minmax(0, 1fr);
    margin: var(--spacing-3) 0;
    padding: var(--spacing-4);
  }

  .notification-actions {
    grid-column: 1 / -1;
    flex-direction: row;
    flex-wrap: wrap;
    justify-content: flex-end;
    width: 100%;
  }

  .notification-title-row {
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .title-stack h3 {
    white-space: normal;
  }
}
</style>
