export interface NotificationSettings {
  notification_url: string | null
  notifications_enabled: boolean
  apprise_docs_url: string
  notify_online_global: boolean
  notify_offline_global: boolean
  notify_update_global: boolean
}

export interface StreamerNotificationSettings {
  streamer_id: number;
  username?: string;
  profile_image_url?: string;
  notify_online: boolean
  notify_offline: boolean
  notify_update: boolean
}

export interface GlobalSettings {
  notification_url: string;
  notifications_enabled: boolean;
  notify_online_global: boolean;
  notify_offline_global: boolean;
  notify_update_global: boolean;
  apprise_docs_url: string;
}