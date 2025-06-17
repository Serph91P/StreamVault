export interface NotificationSettings {
  notification_url: string | null
  notifications_enabled: boolean
  apprise_docs_url: string
  notify_online_global: boolean
  notify_offline_global: boolean
  notify_update_global: boolean
  notify_favorite_category_global?: boolean
}

export interface StreamerNotificationSettings {
  streamer_id: number;
  username?: string;
  profile_image_url?: string;
  notify_online: boolean;
  notify_offline: boolean;
  notify_update: boolean;
  notify_favorite_category?: boolean;
}

export interface Category {
  id: number;
  twitch_id: string;
  name: string;
  box_art_url: string | null;
  is_favorite: boolean;
  first_seen: string;
  last_seen: string;
}

export interface GlobalSettings {
  notification_url: string;
  notifications_enabled: boolean;
  notify_online_global: boolean;
  notify_offline_global: boolean;
  notify_update_global: boolean;
  http_proxy?: string;
  https_proxy?: string;
  apprise_docs_url: string;
}