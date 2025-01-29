export interface NotificationSettings {
  notification_url: string | null
  notifications_enabled: boolean
  apprise_docs_url: string
}

export interface StreamerNotificationSettings {
  streamer_id: number
  username: string
  notify_online: boolean
  notify_offline: boolean
  notify_update: boolean
}