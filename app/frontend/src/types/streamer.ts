// Types related to streamers

export interface Streamer {
  id: string;
  username: string;
  display_name?: string;
  twitch_id: string;
  profile_image_url?: string;
  is_live: boolean;
  title?: string;
  category_name?: string;
  language?: string;
  last_updated?: string;
  recording_enabled?: boolean;
  is_recording?: boolean;
  auto_record?: boolean;
  record_public?: boolean;
  record_subscribers?: boolean;
  quality?: string;
  
  // Last stream info (shown when offline) - Migration 023
  last_stream_title?: string;
  last_stream_category_name?: string;
  last_stream_viewer_count?: number;
  last_stream_ended_at?: string;  // ISO 8601 datetime
}

export interface StreamerApiResponse {
  streamers: Streamer[];
}

export interface StreamerCreate {
  username: string;
  settings?: {
    notifications?: {
      notify_online?: boolean;
      notify_offline?: boolean;
      notify_update?: boolean;
      notify_favorite_category?: boolean;
    };
    recording?: {
      enabled?: boolean;
      quality?: string;
      custom_filename?: string;
    };
  };
}
