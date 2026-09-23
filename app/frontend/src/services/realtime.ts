import { parseRealtimeEvent } from '@/types/events'
import type { RealtimeEvent } from '@/types/events'

export interface RealtimeReplayWindow {
  since: number
  events: RealtimeEvent<string>[]
  gap: boolean
  latest_event_id: number
  oldest_event_id: number | null
  retained_events: number
  max_retained_events: number
}

export class RealtimeReplayAuthError extends Error {}

export async function fetchRealtimeEvents(since: number): Promise<RealtimeReplayWindow> {
  const response = await fetch(`/api/realtime/events?since=${since}`, {
    credentials: 'include'
  })

  if (response.status === 401 || response.status === 403) {
    throw new RealtimeReplayAuthError('Realtime session is no longer authenticated')
  }
  if (!response.ok) {
    throw new Error(`Failed to replay realtime events: HTTP ${response.status}`)
  }

  const body: unknown = await response.json()
  if (!body || typeof body !== 'object' || !Array.isArray((body as { events?: unknown }).events)) {
    throw new Error('Failed to replay realtime events: invalid response')
  }

  const replay = body as Omit<RealtimeReplayWindow, 'events'> & { events: unknown[] }
  return {
    ...replay,
    events: replay.events.flatMap((event) => {
      const parsed = parseRealtimeEvent(event)
      return parsed ? [parsed] : []
    })
  }
}
