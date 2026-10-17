import type { Stream } from '../../src/types/streams'

// Test-only HTTP boundary for the REAL frontend. No store/history/auth injection.
export const chapterVariants = ['zero', 'default', 'one', 'many', 'long'] as const
export type ChapterVariant = typeof chapterVariants[number]
export const playerViewports = [
  { width: 320, height: 568 }, { width: 360, height: 640 },
  { width: 390, height: 844 }, { width: 568, height: 320 },
  { width: 768, height: 1024 }, { width: 1440, height: 900 },
] as const

export function syntheticChapters(variant: ChapterVariant) {
  const count = { zero: 0, default: 1, one: 1, many: 6, long: 80 }[variant]
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    title: variant === 'default' ? '' : `Synthetic chapter ${index + 1}${variant === 'long' ? ' — a deliberately long accessible chapter title for narrow screens'.repeat(3) : ''}`,
    start: variant === 'default' ? 0 : index * 10 / Math.max(1, count - 1) + 1,
    end: index === count - 1 ? 12 : (index + 1) * 10 / Math.max(1, count - 1) + 1,
  }))
}

export const syntheticStreamer = {
  id: 1, name: 'synthetic_alpha', username: 'synthetic_alpha', display_name: 'Synthetic Alpha',
  twitch_id: 'synthetic-1', is_live: false, is_recording: false,
  is_favorite: false, auto_record: false, last_seen: null,
}
export const syntheticVideos = Array.from({ length: 40 }, (_, index) => ({
  id: index + 1, stream_id: index + 1, streamer_id: 1, streamer_name: 'synthetic_alpha',
  title: `Synthetic alpha recording ${String(index + 1).padStart(2, '0')}`,
  duration: 12, status: 'ready', file_size: 3257,
  created_at: new Date(Date.UTC(2026, 0, index + 1)).toISOString(),
  started_at: new Date(Date.UTC(2026, 0, index + 1)).toISOString(),
  ended_at: new Date(Date.UTC(2026, 0, index + 1, 0, 0, 12)).toISOString(),
  file_path: `/synthetic/${index + 1}.mp4`, recording_path: `/synthetic/${index + 1}.mp4`,
  category_name: 'Synthetic category', events: [],
  language: 'en', twitch_stream_id: null, episode_number: index + 1,
} satisfies Stream & Record<string, unknown>))

/** Unknown requests fail closed instead of returning a plausible empty success. */
export function syntheticReply(path: string, method = 'GET', variant: ChapterVariant = 'default') {
  const pathname = new URL(path, 'http://127.0.0.1').pathname
  let body: unknown
  if (method !== 'GET') return { status: 405, body: { detail: 'Synthetic fixture is read-only' } }
  if (pathname === '/auth/setup') body = { setup_required: false, welcome_completed: true }
  else if (pathname === '/auth/check') body = { authenticated: true }
  else if (pathname === '/api/videos') body = syntheticVideos
  else if (/^\/api\/videos\/\d+\/chapters$/.test(pathname)) body = syntheticChapters(variant)
  else if (pathname === '/api/streamers') body = { streamers: [syntheticStreamer] }
  else if (pathname === '/api/streamers/streamer/1') body = syntheticStreamer
  else if (pathname === '/api/streamers/1/streams') body = { streams: syntheticVideos }
  else if (/^\/api\/stream\/\d+\/has-recording$/.test(pathname)) body = { has_recording: true }
  else if (pathname === '/api/status/system') body = { system: { active_recordings: 0, total_streamers: 1, live_streamers: 0, timestamp: '2026-01-01T00:00:00Z' } }
  else if (pathname === '/api/status/streamers') body = { streamers: [syntheticStreamer] }
  else if (pathname === '/api/status/streams') body = { streams: syntheticVideos }
  else if (pathname === '/api/status/active-recordings' || pathname === '/api/recording/active') body = { active_recordings: [] }
  else if (pathname === '/api/status/notifications') body = { notification_system: { enabled: false }, recent_events: [] }
  else if (pathname === '/api/notifications/state') body = { last_read: null, last_cleared: null }
  else if (pathname === '/api/realtime/events') body = { since: 0, events: [], gap: false, latest_event_id: 0, oldest_event_id: null, retained_events: 0, max_retained_events: 0 }
  else if (pathname === '/api/background-queue/stats') body = { total_tasks: 0, pending_tasks: 0, active_tasks: 0, completed_tasks: 0, failed_tasks: 0, retried_tasks: 0, workers: 0, is_running: false }
  else if (pathname === '/api/background-queue/active-tasks' || pathname === '/api/background-queue/recent-tasks') body = []
  else if (pathname === '/api/version') body = { version: 'synthetic-test-only', frontend_version: 'synthetic-test-only' }
  else return { status: 501, body: { detail: `Unspecified synthetic endpoint: ${pathname}` } }
  return { status: 200, body }
}
