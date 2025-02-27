export interface Stream {
  id: number
  streamer_id: number
  started_at: string | null
  ended_at: string | null
  title: string | null
  category_name: string | null
  language: string | null
  twitch_stream_id: string | null
}

export interface StreamerInfo {
  id: number
  username: string
  profile_image_url: string | null
}
