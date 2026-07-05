import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { notificationApi } from '@/services/api'
import {
  readNotifications,
  writeNotifications,
  clearNotificationsStorage,
  type StoredNotification
} from '@/services/notificationStorage'
import type { CanonicalNotificationEvent } from '@/types/events'

export type NotificationFilter = 'all' | 'unread' | 'info' | 'success' | 'warning' | 'error' | 'critical' | string

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref<StoredNotification[]>([])
  const filter = ref<NotificationFilter>('all')

  function notificationIdentity(notification: Pick<StoredNotification, 'event_id' | 'dedupe_key' | 'type' | 'timestamp'>): string {
    const eventId = notification.event_id?.trim()
    if (eventId) return `event:${eventId}`

    const dedupeKey = notification.dedupe_key?.trim()
    if (dedupeKey) return `dedupe:${dedupeKey}`

    return `fallback:${notification.type}:${notification.timestamp}`
  }

  const sortedNotifications = computed(() => {
    return [...notifications.value].sort((a, b) => {
      return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    })
  })

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
      (n) => n.type === filter.value || n.severity === filter.value
    )
  })

  function setFilter(nextFilter: NotificationFilter): void {
    filter.value = nextFilter
  }

  function load(): void {
    notifications.value = readNotifications()
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
          writeNotifications(notifications.value)
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

    const newIdentity = notificationIdentity(newNotification)
    const existingIndex = notifications.value.findIndex((n) => notificationIdentity(n) === newIdentity)

    if (existingIndex >= 0) {
      newNotification.read = notifications.value[existingIndex].read
      newNotification.read_at = notifications.value[existingIndex].read_at
      notifications.value[existingIndex] = newNotification
    } else {
      notifications.value.unshift(newNotification)
    }

    if (notifications.value.length > 100) {
      notifications.value = notifications.value.slice(0, 100)
    }

    writeNotifications(notifications.value)
  }

  function markAllRead(): void {
    const now = new Date().toISOString()
    notifications.value.forEach((n) => {
      n.read = true
      n.read_at = n.read_at || now
    })
    writeNotifications(notifications.value)

    notificationApi.markRead(now).catch((error) => {
      console.error('Failed to mark notifications as read on backend:', error)
    })
  }

  function markRead(id: string): void {
    const n = notifications.value.find((n) => n.id === id)
    if (n && !n.read) {
      n.read = true
      n.read_at = new Date().toISOString()
      writeNotifications(notifications.value)
    }
  }

  function markUnread(id: string): void {
    const n = notifications.value.find((n) => n.id === id)
    if (n) {
      n.read = false
      n.read_at = undefined
      writeNotifications(notifications.value)
    }
  }

  function remove(id: string): void {
    notifications.value = notifications.value.filter((n) => n.id !== id)
    writeNotifications(notifications.value)
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
