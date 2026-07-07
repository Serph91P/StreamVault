export const REALTIME_EVENT_TYPES = [
  'active_recordings_update',
  'background_queue_update',
  'category_change',
  'channel.update',
  'connection.status',
  'notification_event',
  'proxy_health_update',
  'queue_stats_update',
  'recording.available',
  'recording.completed',
  'recording.failed',
  'recording.finished',
  'recording.started',
  'recording.status_update',
  'recording.stopped',
  'recording_available',
  'recording_completed',
  'recording_failed',
  'recording_finished',
  'recording_started',
  'recording_status_update',
  'recording_stopped',
  'stream.offline',
  'stream.online',
  'stream.update',
  'stream_offline',
  'stream_online',
  'streamer.added',
  'streamer.removed',
  'streamer_offline',
  'streamer_online',
  'streamers_update',
  'streams_update',
  'task_progress_update',
  'task_status_update',
  'test',
  'test_local',
  'toast_notification'
] as const

export type RealtimeEventType = typeof REALTIME_EVENT_TYPES[number]

export const CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS = {
  recording_available: 'recording.available',
  recording_completed: 'recording.completed',
  recording_failed: 'recording.failed',
  recording_finished: 'recording.finished',
  recording_started: 'recording.started',
  recording_status_update: 'recording.status_update',
  recording_stopped: 'recording.stopped',
  stream_offline: 'stream.offline',
  stream_online: 'stream.online',
  streamer_offline: 'streamer_offline',
  streamer_online: 'streamer_online'
} as const satisfies Partial<Record<RealtimeEventType, RealtimeEventType>>

export type CanonicalRealtimeEventType = Exclude<
  RealtimeEventType,
  keyof typeof CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS
>

export interface RealtimeEventBase<
  TType extends string = RealtimeEventType,
  TData = any
> {
  type: TType
  data?: TData
  message?: string
  timestamp?: string | number
  [key: string]: unknown
}

export type RealtimeEvent<TType extends string = RealtimeEventType> =
  RealtimeEventBase<TType>

export const NOTIFICATION_SEVERITIES = ['info', 'success', 'warning', 'error', 'critical'] as const
export type NotificationSeverity = typeof NOTIFICATION_SEVERITIES[number]

export const NOTIFICATION_SOURCES = ['websocket', 'push', 'apprise', 'system', 'test'] as const
export type NotificationSource = typeof NOTIFICATION_SOURCES[number]

export interface NotificationAction {
  id: string
  label: string
  target_url?: string
}

export interface CanonicalNotificationEvent {
  event_id: string
  dedupe_key: string
  type: string
  severity: NotificationSeverity
  title: string
  body: string
  created_at: string
  source: NotificationSource
  target_url?: string
  streamer_id?: string | number
  streamer_name?: string
  recording_id?: string | number
  video_id?: string | number
  actions: NotificationAction[]
  data: Record<string, unknown>
}

const realtimeEventTypes = new Set<string>(REALTIME_EVENT_TYPES)
const notificationEventTypes = new Set<string>([
  'stream.online',
  'stream.offline',
  'channel.update',
  'stream.update',
  'recording.started',
  'recording.completed',
  'recording.failed',
  'recording.finished',
  'recording.available',
  'test',
  'notification_event'
])

export function isRealtimeEventType(type: string): type is RealtimeEventType {
  return realtimeEventTypes.has(type)
}

export function normalizeRealtimeEventType(type: string): string {
  if (isRealtimeEventType(type) && type in CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS) {
    return CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS[
      type as keyof typeof CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS
    ]
  }

  return type
}

export function hasRealtimeEventType(
  event: Pick<RealtimeEventBase<string>, 'type'> | null | undefined,
  ...types: RealtimeEventType[]
): boolean {
  if (!event?.type) {
    return false
  }

  const actualType = normalizeRealtimeEventType(event.type)
  return types.some((type) => actualType === normalizeRealtimeEventType(type))
}

export function isCanonicalNotificationType(type: string): boolean {
  return notificationEventTypes.has(normalizeRealtimeEventType(type))
}

export function isNotificationRealtimeEvent(
  event: Pick<RealtimeEventBase<string>, 'type'> | null | undefined
): boolean {
  return Boolean(event?.type && isCanonicalNotificationType(event.type))
}

export function parseRealtimeEvent(raw: unknown): RealtimeEvent<string> | null {
  if (!raw || typeof raw !== 'object' || !('type' in raw)) {
    return null
  }

  const event = raw as { type?: unknown }
  if (typeof event.type !== 'string') {
    return null
  }

  return raw as RealtimeEvent<string>
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {}
}

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value
    }
  }
}

function firstId(...values: unknown[]): string | number | undefined {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value
    }
  }
}

function normalizeNotificationSource(source: unknown): NotificationSource {
  if (typeof source === 'string' && (NOTIFICATION_SOURCES as readonly string[]).includes(source)) {
    return source as NotificationSource
  }

  return 'websocket'
}

function toIsoString(value: unknown): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Date(value).toISOString()
  }

  if (typeof value === 'string' && value.trim()) {
    const numeric = Number(value)
    const date = Number.isFinite(numeric) ? new Date(numeric) : new Date(value)
    if (!Number.isNaN(date.getTime())) {
      return date.toISOString()
    }
  }

  return new Date().toISOString()
}

export function normalizeNotificationTargetUrl(target: string): string {
  try {
    const parsed = new URL(target, window.location.origin)
    if (parsed.origin === window.location.origin) {
      const streamerMatch = parsed.pathname.match(/^\/streamer\/([^/]+)\/?$/)
      if (streamerMatch) {
        parsed.pathname = `/streamers/${streamerMatch[1]}`
      }

      return `${parsed.pathname}${parsed.search}${parsed.hash}`
    }
  } catch (_error) {
    return target
  }

  return target
}

function makeTargetUrl(data: Record<string, unknown>, type: string): string | undefined {
  const target = firstString(data.target_url, data.internal_url)
  if (target) {
    return normalizeNotificationTargetUrl(target)
  }

  const videoId = firstId(data.video_id, data.videoId)
  if (videoId !== undefined) {
    return `/videos/${videoId}`
  }

  const streamerId = firstId(data.streamer_id, data.streamerId)
  const streamId = firstId(data.stream_id, data.streamId)
  if (
    (type === 'recording.finished' || type === 'recording.completed') &&
    streamerId !== undefined &&
    streamId !== undefined
  ) {
    return `/streamer/${streamerId}/stream/${streamId}/watch`
  }

  if (streamerId !== undefined) {
    return `/streamers/${streamerId}`
  }
}

function severityForType(type: string, data: Record<string, unknown>): NotificationSeverity {
  const severity = firstString(data.severity)
  if (severity && (NOTIFICATION_SEVERITIES as readonly string[]).includes(severity)) {
    return severity as NotificationSeverity
  }

  if (type === 'recording.failed') {
    return 'critical'
  }
  if (type === 'recording.completed' || type === 'recording.finished' || type === 'recording.available') {
    return 'success'
  }
  if (type === 'stream.offline') {
    return 'warning'
  }
  return 'info'
}

function titleForType(type: string, data: Record<string, unknown>, streamerName: string): string {
  const title = firstString(data.notification_title)
  if (title) {
    return title
  }

  switch (type) {
    case 'stream.online':
      return `${streamerName} is Live`
    case 'stream.offline':
      return `${streamerName} Stream Ended`
    case 'channel.update':
    case 'stream.update':
      return `${streamerName} Updated Stream`
    case 'recording.started':
      return 'Recording Started'
    case 'recording.completed':
    case 'recording.finished':
    case 'recording.available':
      return 'Recording Completed'
    case 'recording.failed':
      return 'Recording Failed'
    case 'test':
      return 'Test Notification'
    default:
      return 'Notification'
  }
}

function bodyForType(type: string, data: Record<string, unknown>, streamerName: string): string {
  const body = firstString(data.body, data.notification_body, data.message)
  if (body) {
    return body
  }

  const streamTitle = firstString(data.stream_title, data.title)
  switch (type) {
    case 'stream.online':
      return streamTitle ? `${streamerName} is live: "${streamTitle}"` : `${streamerName} is now streaming`
    case 'stream.offline':
      return `${streamerName} has gone offline`
    case 'channel.update':
    case 'stream.update':
      return streamTitle ? `New title: ${streamTitle}` : `${streamerName} updated their stream`
    case 'recording.started':
      return `Started recording ${streamerName}'s stream`
    case 'recording.completed':
    case 'recording.finished':
    case 'recording.available':
      return `Successfully completed recording ${streamerName}'s stream`
    case 'recording.failed':
      return `Recording failed for ${streamerName}: ${firstString(data.error_message, data.error) || 'Unknown error'}`
    case 'test':
      return 'This is a test notification to verify the system is working properly'
    default:
      return `New notification for ${streamerName}`
  }
}

export function toCanonicalNotificationEvent(
  event: RealtimeEventBase<string> | null | undefined
): CanonicalNotificationEvent | null {
  if (!event?.type) {
    return null
  }

  const type = normalizeRealtimeEventType(event.type)
  const data = asRecord(event.data)

  if (!isCanonicalNotificationType(type)) {
    return null
  }

  if (type === 'notification_event') {
    const eventId = firstString(data.event_id, data.id)
    const dedupeKey = firstString(data.dedupe_key, data.dedupeKey, eventId)
    const notificationType = firstString(data.type) || type
    const title = firstString(data.title)
    const body = firstString(data.body, data.message)
    if (!eventId || !dedupeKey || !title || !body) {
      return null
    }

    return {
      event_id: eventId,
      dedupe_key: dedupeKey,
      type: notificationType,
      severity: severityForType(notificationType, data),
      title,
      body,
      created_at: toIsoString(data.created_at || data.timestamp),
      source: normalizeNotificationSource(data.source),
      target_url: makeTargetUrl(data, notificationType),
      streamer_id: firstId(data.streamer_id, data.streamerId),
      streamer_name: firstString(data.streamer_name, data.username),
      recording_id: firstId(data.recording_id, data.recordingId),
      video_id: firstId(data.video_id, data.videoId),
      actions: [],
      data
    }
  }

  const streamerId = firstId(data.streamer_id, data.streamerId)
  const streamerName = firstString(data.streamer_name, data.username) || 'Unknown'
  const recordingId = firstId(data.recording_id, data.recordingId, data.stream_id, data.streamId)
  const videoId = firstId(data.video_id, data.videoId)
  const createdAt = toIsoString(data.created_at || data.timestamp || event.timestamp)
  const targetUrl = makeTargetUrl(data, type)
  const dedupeKey = firstString(data.dedupe_key, data.dedupeKey) || [
    type,
    streamerId ?? streamerName,
    recordingId ?? videoId ?? firstString(data.title, data.stream_title) ?? createdAt
  ].join(':')

  return {
    event_id: firstString(data.event_id, data.id, data.test_id) || dedupeKey,
    dedupe_key: dedupeKey,
    type,
    severity: severityForType(type, data),
    title: titleForType(type, data, streamerName),
    body: bodyForType(type, data, streamerName),
    created_at: createdAt,
    source: type === 'test' ? 'test' : 'websocket',
    target_url: targetUrl,
    streamer_id: streamerId,
    streamer_name: streamerName,
    recording_id: recordingId,
    video_id: videoId,
    actions: targetUrl ? [{ id: 'open', label: 'Open', target_url: targetUrl }] : [],
    data
  }
}
