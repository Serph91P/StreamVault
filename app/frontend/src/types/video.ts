export type VideoDeleteOutcome = PromiseSettledResult<unknown> & { id: number }

export interface CatalogVideo {
  id: number
  title?: string | null
  streamer_id?: number
  streamer_name?: string
  category_name?: string | null
  duration?: number | null
  file_size?: number
  file_path?: string | null
  created_at?: string | null
  recorded_at?: string | null
  started_at?: string | null
  stream_date?: string | null
  thumbnail_url?: string | null
  view_count?: number
  viewer_count?: number
  is_recording?: boolean
  status?: string
}

export interface VideoCatalogQuery {
  page?: number
  page_size?: number
  q?: string
  streamer_id?: number
  category?: string
  streamer?: string
  recording?: boolean
  sort?: 'date' | 'title' | 'streamer' | 'duration' | 'size'
  order?: 'asc' | 'desc'
  created_from?: string
  created_before?: string
  duration?: 'short' | 'medium' | 'long'
}

export interface VideoCatalogPage {
  items: CatalogVideo[]
  total: number
  page: number
  page_size: number
  has_more: boolean
  index: {
    pending: number
    missing: number
    error: number
    complete: boolean
    oldest_checked_at: string | null
    page_revalidation_changed: boolean
    retry_required: boolean
  }
  summary: {
    total: number
    duration: number
    file_size: number
    streamers: { id: number; name: string; count: number }[]
    categories: string[]
  }
}
