// Types related to streamers

export interface Streamer {
  id: number;
  username: string;
  twitch_id: string;
  profile_image_url?: string;
  is_live: boolean;
  is_recording: boolean;
  recording_enabled?: boolean;
  active_stream_id?: number | null;
  title?: string | null;
  category_name?: string | null;
  language?: string | null;
  last_updated?: string | null;
  original_profile_image_url?: string | null;
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