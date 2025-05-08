// Types related to streamers

export interface Streamer {
  username: string;
  display_name?: string;
  twitch_id?: string;
  auto_record?: boolean;
  record_public?: boolean;
  record_subscribers?: boolean;
  quality?: string;
  profile_image_url?: string;
  is_live?: boolean;
  last_online?: string;
  created_at?: string;
}

export interface StreamerApiResponse {
  streamers: Streamer[];
}