import {
  NOTIFICATION_SEVERITIES,
  NOTIFICATION_SOURCES,
  type NotificationSeverity,
  type NotificationSource,
  type NotificationAction
} from '@/types/events'
import { appStorage } from '@/services/storage'

const MAX_NOTIFICATIONS = 100

export interface StoredNotification {
  id: string
  event_id: string
  dedupe_key: string
  type: string
  severity: NotificationSeverity
  title: string
  body: string
  timestamp: string
  created_at: string
  source: NotificationSource
  target_url?: string
  streamer_id?: string | number
  streamer_username?: string
  streamer_name?: string
  recording_id?: string | number
  video_id?: string | number
  actions: NotificationAction[]
  data: Record<string, unknown>
  read: boolean
  read_at?: string
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function asSeverity(value: unknown): NotificationSeverity {
  return typeof value === 'string' && (NOTIFICATION_SEVERITIES as readonly string[]).includes(value)
    ? value as NotificationSeverity
    : 'info'
}

function asSource(value: unknown): NotificationSource {
  return typeof value === 'string' && (NOTIFICATION_SOURCES as readonly string[]).includes(value)
    ? value as NotificationSource
    : 'websocket'
}

function stableNotificationId(entry: Record<string, unknown>): string {
  const eventId = asString(entry.event_id)
  if (eventId) return eventId

  const id = asString(entry.id)
  if (id) return id

  const dedupeKey = asString(entry.dedupe_key)
  if (dedupeKey) return dedupeKey

  return `${asString(entry.type, 'notification')}:${asString(entry.timestamp, new Date().toISOString())}`
}

function migrateLegacy(notifications: unknown[]): StoredNotification[] {
  const legacyReadTimestamp = Number(appStorage.legacyReadTimestamp || 0)

  return notifications.map((n) => {
    const entry = n as Record<string, unknown>
    if (!entry.timestamp) {
      entry.timestamp = entry.created_at || new Date().toISOString()
    }
    if (!entry.created_at) {
      entry.created_at = entry.timestamp
    }
    if (!entry.type) {
      entry.type = 'notification'
    }
    if (!entry.id) {
      entry.id = stableNotificationId(entry)
    }
    if (!entry.event_id) {
      entry.event_id = asString(entry.id)
    }
    if (!entry.dedupe_key) {
      entry.dedupe_key = asString(entry.event_id) || `${entry.type}:${entry.timestamp}`
    }
    if (!entry.title) {
      entry.title = 'Notification'
    }
    if (!entry.body) {
      entry.body = asString(entry.message, '')
    }
    entry.severity = asSeverity(entry.severity)
    entry.source = asSource(entry.source)
    entry.actions = Array.isArray(entry.actions) ? entry.actions : []
    entry.data = asRecord(entry.data)
    if (entry.read === undefined) {
      const entryTimestamp = new Date(String(entry.timestamp)).getTime()
      entry.read = Number.isFinite(entryTimestamp) && entryTimestamp <= legacyReadTimestamp
    }
    if (!entry.streamer_username && entry.streamer_name) {
      entry.streamer_username = entry.streamer_name
    }
    return entry as unknown as StoredNotification
  })
}

export function readNotifications(): StoredNotification[] {
  try {
    const raw = appStorage.notifications
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return migrateLegacy(parsed)
  } catch {
    return []
  }
}

export function writeNotifications(notifications: StoredNotification[]): void {
  try {
    appStorage.setNotifications(JSON.stringify(notifications.slice(0, MAX_NOTIFICATIONS)))
  } catch (error) {
    console.error('Failed to save notifications:', error)
  }
}

export function clearNotificationsStorage(): void {
  try {
    appStorage.clearNotifications()
  } catch (error) {
    console.error('Failed to clear notifications:', error)
  }
}
