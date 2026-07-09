import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { notificationApi } from '@/services/api'
import {
  readNotifications,
  writeNotifications,
  clearNotificationsStorage,
  type StoredNotification
} from '@/services/notificationStorage'
import { NOTIFICATION_SEVERITIES, type CanonicalNotificationEvent } from '@/types/events'

export type NotificationFilter = 'all' | 'unread' | 'info' | 'success' | 'warning' | 'error' | 'critical' | string

export interface NotificationTypeOption {
  value: string
  label: string
  count: number
}

export interface NotificationSourceOption {
  value: string
  label: string
  count: number
}

export interface NotificationGroup {
  key: string
  title: string
  notifications: StoredNotification[]
  unreadCount: number
}

const MAX_NOTIFICATIONS = 100

export function notificationIdentity(notification: Pick<StoredNotification, 'event_id' | 'dedupe_key' | 'type' | 'timestamp'>): string {
  const eventId = notification.event_id?.trim()
  if (eventId) return `event:${eventId}`

  const dedupeKey = notification.dedupe_key?.trim()
  if (dedupeKey) return `dedupe:${dedupeKey}`

  return `fallback:${notification.type}:${notification.timestamp}`
}

function hasSameNotificationIdentity(
  left: Pick<StoredNotification, 'event_id' | 'dedupe_key' | 'type' | 'timestamp'>,
  right: Pick<StoredNotification, 'event_id' | 'dedupe_key' | 'type' | 'timestamp'>
): boolean {
  const leftEventId = left.event_id?.trim()
  const rightEventId = right.event_id?.trim()
  if (leftEventId && rightEventId && leftEventId === rightEventId) return true

  const leftDedupeKey = left.dedupe_key?.trim()
  const rightDedupeKey = right.dedupe_key?.trim()
  if (leftDedupeKey && rightDedupeKey && leftDedupeKey === rightDedupeKey) return true

  return `${left.type}:${left.timestamp}` === `${right.type}:${right.timestamp}`
}

function compareNewestFirst(a: Pick<StoredNotification, 'timestamp'>, b: Pick<StoredNotification, 'timestamp'>): number {
  return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
}

function sortedLimited(items: StoredNotification[]): StoredNotification[] {
  return [...items].sort(compareNewestFirst).slice(0, MAX_NOTIFICATIONS)
}

function notificationGroupTitle(timestamp: string): string {
  const eventDate = new Date(timestamp)
  if (Number.isNaN(eventDate.getTime())) {
    return 'Earlier'
  }

  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const eventDay = new Date(eventDate)
  eventDay.setHours(0, 0, 0, 0)
  const daysAgo = Math.floor((today.getTime() - eventDay.getTime()) / 86400000)

  if (daysAgo <= 0) return 'Today'
  if (daysAgo === 1) return 'Yesterday'
  if (daysAgo < 7) return eventDate.toLocaleDateString(undefined, { weekday: 'long' })
  return 'Earlier'
}

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref<StoredNotification[]>([])
  const filter = ref<NotificationFilter>('all')

  const sortedNotifications = computed(() => sortedLimited(notifications.value))

  const unreadCount = computed(() => {
    return notifications.value.filter((n) => !n.read).length
  })

  const totalCount = computed(() => notifications.value.length)

  const filteredNotifications = computed(() => {
    if (filter.value === 'all') return sortedNotifications.value
    if (filter.value === 'unread') {
      return sortedNotifications.value.filter((n) => !n.read)
    }
    return sortedNotifications.value.filter(
      (n) => n.type === filter.value || n.severity === filter.value || n.source === filter.value
    )
  })

  const severityCounts = computed<Record<string, number>>(() => {
    return sortedNotifications.value.reduce<Record<string, number>>((counts, notification) => {
      counts[notification.severity] = (counts[notification.severity] || 0) + 1
      return counts
    }, Object.fromEntries(NOTIFICATION_SEVERITIES.map((severity) => [severity, 0])) as Record<string, number>)
  })

  const typeOptions = computed<NotificationTypeOption[]>(() => {
    const counts = sortedNotifications.value.reduce<Record<string, number>>((result, notification) => {
      result[notification.type] = (result[notification.type] || 0) + 1
      return result
    }, {})

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([value, count]) => ({
        value,
        count,
        label: value.replaceAll('.', ' ')
      }))
  })

  const sourceOptions = computed<NotificationSourceOption[]>(() => {
    const labels: Record<string, string> = {
      websocket: 'WebSocket',
      push: 'Push',
      apprise: 'Apprise',
      system: 'System',
      test: 'Test'
    }

    const counts = sortedNotifications.value.reduce<Record<string, number>>((result, notification) => {
      result[notification.source] = (result[notification.source] || 0) + 1
      return result
    }, {})

    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([value, count]) => ({
        value,
        count,
        label: labels[value] || value
      }))
  })

  const groupedNotifications = computed<NotificationGroup[]>(() => {
    const groups = new Map<string, NotificationGroup>()

    filteredNotifications.value.forEach((notification) => {
      const groupTitle = notificationGroupTitle(notification.timestamp)
      const groupKey = groupTitle.toLowerCase().replace(/[^a-z0-9]+/g, '-')
      const group = groups.get(groupKey) || {
        key: groupKey,
        title: groupTitle,
        notifications: [],
        unreadCount: 0
      }

      group.notifications.push(notification)
      if (!notification.read) {
        group.unreadCount += 1
      }
      groups.set(groupKey, group)
    })

    return Array.from(groups.values())
  })

  function persist(): void {
    notifications.value = sortedLimited(notifications.value)
    writeNotifications(notifications.value)
  }

  function setFilter(nextFilter: NotificationFilter): void {
    filter.value = nextFilter
  }

  function load(): void {
    notifications.value = sortedLimited(readNotifications())
    writeNotifications(notifications.value)
  }

  async function syncBackendState(): Promise<void> {
    try {
      const backendState = await notificationApi.getState()
      const clearedTs =
        (backendState as Record<string, unknown>).last_cleared_timestamp ||
        (backendState as Record<string, unknown>).last_cleared
      if (clearedTs) {
        const cleared = new Date(clearedTs as string).getTime()
        const before = notifications.value.length
        notifications.value = notifications.value.filter((n) => {
          return new Date(n.timestamp).getTime() > cleared
        })
        if (notifications.value.length !== before) {
          persist()
        }
      }

      const readTs =
        (backendState as Record<string, unknown>).last_read_timestamp ||
        (backendState as Record<string, unknown>).last_read
      if (readTs) {
        const readAt = new Date(readTs as string).getTime()
        let changed = false
        notifications.value.forEach((n) => {
          const notificationTime = new Date(n.timestamp).getTime()
          if (!n.read && Number.isFinite(notificationTime) && notificationTime <= readAt) {
            n.read = true
            n.read_at = n.read_at || readTs as string
            changed = true
          }
        })
        if (changed) {
          persist()
        }
      }
    } catch (error) {
      console.error('Failed to sync backend notification state:', error)
    }
  }

  function addFromEvent(notificationEvent: CanonicalNotificationEvent): void {
    const newNotification: StoredNotification = {
      id: notificationEvent.event_id,
      event_id: notificationEvent.event_id,
      dedupe_key: notificationEvent.dedupe_key,
      type: notificationEvent.type,
      severity: notificationEvent.severity,
      title: notificationEvent.title,
      body: notificationEvent.body,
      timestamp: notificationEvent.created_at,
      created_at: notificationEvent.created_at,
      source: notificationEvent.source,
      target_url: notificationEvent.target_url,
      streamer_id: notificationEvent.streamer_id,
      streamer_username: notificationEvent.streamer_name || 'Unknown',
      streamer_name: notificationEvent.streamer_name,
      recording_id: notificationEvent.recording_id,
      video_id: notificationEvent.video_id,
      actions: notificationEvent.actions,
      data: notificationEvent.data,
      read: false
    }

    const existingIndex = notifications.value.findIndex((n) => hasSameNotificationIdentity(n, newNotification))

    if (existingIndex >= 0) {
      newNotification.read = notifications.value[existingIndex].read
      newNotification.read_at = notifications.value[existingIndex].read_at
      notifications.value[existingIndex] = newNotification
    } else {
      notifications.value.unshift(newNotification)
    }

    persist()
  }

  function markAllRead(): void {
    const now = new Date().toISOString()
    notifications.value.forEach((n) => {
      n.read = true
      n.read_at = n.read_at || now
    })
    persist()

    notificationApi.markRead(now).catch((error) => {
      console.error('Failed to mark notifications as read on backend:', error)
    })
  }

  function markRead(id: string): void {
    const n = notifications.value.find((n) => n.id === id)
    if (n && !n.read) {
      n.read = true
      n.read_at = new Date().toISOString()
      persist()

      notificationApi.markRead(n.read_at).catch((error) => {
        console.error('Failed to mark notification as read on backend:', error)
      })
    }
  }

  function markUnread(id: string): void {
    const n = notifications.value.find((n) => n.id === id)
    if (n) {
      n.read = false
      n.read_at = undefined
      persist()
    }
  }

  function remove(id: string): void {
    notifications.value = notifications.value.filter((n) => n.id !== id)
    persist()
  }

  async function clearAll(): Promise<void> {
    try {
      await notificationApi.clear()
    } catch (error) {
      console.error('Failed to clear notifications on backend:', error)
    }
    notifications.value = []
    clearNotificationsStorage()
  }

  return {
    notifications,
    filter,
    setFilter,
    sortedNotifications,
    unreadCount,
    totalCount,
    filteredNotifications,
    severityCounts,
    typeOptions,
    sourceOptions,
    groupedNotifications,
    load,
    syncBackendState,
    addFromEvent,
    markAllRead,
    markRead,
    markUnread,
    remove,
    clearAll
  }
})
