import type { NotificationSeverity, NotificationSource, NotificationAction } from '@/types/events'
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
  data: Record<string, any>
  read: boolean
  read_at?: string
}

function migrateLegacy(notifications: unknown[]): StoredNotification[] {
  const legacyReadTimestamp = Number(appStorage.legacyReadTimestamp || 0)

  return notifications.map((n) => {
    const entry = n as Record<string, unknown>
    if (!entry.timestamp) {
      entry.timestamp = entry.created_at || new Date().toISOString()
    }
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
