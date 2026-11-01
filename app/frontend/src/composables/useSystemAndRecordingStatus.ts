/**
 * Recording & System Status Composable
 * 
 * Provides current system status, active recordings, and streamer data
 * using both WebSocket (for live updates) and REST API (for guaranteed current state).
 * 
 * This ensures the frontend always has current status, even if:
 * - WebSocket connection is lost
 * - User opens the frontend while offline
 * - Network connectivity issues occur
 * 
 * Note: Background Queue data is handled separately by useBackgroundQueue.ts
 */

import { ref, computed, getCurrentScope, shallowReactive, onMounted, onUnmounted, onScopeDispose, watch, readonly } from 'vue'
import { defineStore } from 'pinia'
import { useRealtimeStore } from '@/stores/realtime'
import { systemApi } from '@/services/api'
import { logError } from '@/utils/logger'
import type { RealtimeEvent } from '@/types/events'

// Mock mode check
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'

interface SystemStatus {
  active_recordings: number
  total_streamers: number
  live_streamers: number
  timestamp: string
}

interface ActiveRecording {
  id: number
  stream_id: number
  streamer_id: number
  streamer_name: string
  title: string
  started_at: string
  file_path: string
  status: string
  duration: number
}

interface StreamerStatus {
  id: number
  name: string
  display_name: string
  twitch_id: string
  profile_image_url?: string
  is_live: boolean
  is_recording: boolean
  is_favorite: boolean
  auto_record: boolean
  last_seen: string | null
  current_title: string | null
  current_category: string | null
  // Add missing properties for WebSocket data
  language?: string
  last_title?: string
  last_category?: string
}

interface StreamStatus {
  id: number
  streamer_name: string
  title: string
  category: string
  is_live: boolean
  has_recording: boolean
  recording_status: string | null
  started_at: string | null
  duration: number | null
}

interface NotificationStatus {
  notification_system: {
    enabled: boolean
    url_configured: boolean
    active_subscriptions: number
    streamers_with_notifications: number
  }
  recent_events: any[]
  timestamp: string
}

const useSystemStatusStore = defineStore('systemStatus', () => {
  const ownerScope = getCurrentScope()!
  // App binds the existing auth lifecycle once; consumers never initiate auth checks.
  let enabled = false
  let consumers = 0
  let stopOwner: (() => void) | undefined
  let generation = 0
  const inFlight = shallowReactive(new Map<object, Promise<void>>())
  const resourceErrors = shallowReactive(new Map<object, string>())

  // State
  const systemStatus = ref<SystemStatus | null>(null)
  const activeRecordings = ref<ActiveRecording[]>([])
  const streamersStatus = ref<StreamerStatus[]>([])
  const streamsStatus = ref<StreamStatus[]>([])
  const notificationsStatus = ref<NotificationStatus | null>(null)
  const isLoading = computed(() => inFlight.size > 0)
  const error = computed(() => [...resourceErrors.values()].join('; ') || null)
  const lastUpdate = ref<Date | null>(null)
  
  // WebSocket integration via central store
  const realtime = useRealtimeStore()
  const realtimeUnsubs: Array<() => void> = []
  
  // Computed properties
  const isOnline = computed(() => realtime.connectionStatus === 'connected')
  const hasActiveRecordings = computed(() => activeRecordings.value.length > 0)
  const activeRecordingsCount = computed(() => activeRecordings.value.length)
  
  // Each API method identifies one resource and shares only its current read.
  function createFetcher<T>(request: (params: Record<string, number>) => Promise<T>, apply: (data: T) => void) {
    return (useCache = true): Promise<void> => {
      if (!stopOwner) return Promise.resolve()
      const existing = inFlight.get(request)
      if (existing) return existing
      const startedGeneration = generation
      const promise = (async () => {
        try {
          const data = await request(useCache ? {} : { t: Date.now() })
          if (startedGeneration !== generation) return
          apply(data)
          resourceErrors.delete(request)
          lastUpdate.value = new Date()
        } catch (err) {
          if (startedGeneration !== generation) return
          resourceErrors.set(request, err instanceof Error ? err.message : 'Unknown error')
          logError('systemStatus', request.name, err)
        } finally {
          if (startedGeneration === generation) inFlight.delete(request)
        }
      })()
      inFlight.set(request, promise)
      return promise
    }
  }

  const fetchSystemStatus = createFetcher(systemApi.getStatus, data => { systemStatus.value = data.system })
  const fetchActiveRecordings = createFetcher(systemApi.getActiveRecordingsStatus, data => { activeRecordings.value = data.active_recordings || [] })
  const fetchStreamersStatus = createFetcher(systemApi.getStreamersStatus, data => { streamersStatus.value = data.streamers || [] })
  const fetchStreamsStatus = createFetcher(systemApi.getStreamsStatus, data => { streamsStatus.value = data.streams || [] })
  const fetchNotificationsStatus = createFetcher(systemApi.getNotificationsStatus, data => { notificationsStatus.value = data })
  
  // Fetch all status data
  const fetchAllStatus = async (useCache = true): Promise<void> => {
    if (!stopOwner) return
    // Mock mode: populate with realistic data without hitting backend
    if (USE_MOCK_DATA) {
      systemStatus.value = {
        active_recordings: 1,
        total_streamers: 4,
        live_streamers: 2,
        timestamp: new Date().toISOString()
      }
      activeRecordings.value = [{
        id: 1, stream_id: 101, streamer_id: 1, streamer_name: 'streamer_alpha',
        title: 'Just Chatting with Chat!', started_at: new Date(Date.now() - 3600000).toISOString(),
        file_path: '/recordings/streamer_alpha/2025-03-14.mp4', status: 'recording', duration: 3600
      }]
      streamersStatus.value = [
        { id: 1, name: 'streamer_alpha', display_name: 'Streamer Alpha', twitch_id: '12345', is_live: true, is_recording: true, is_favorite: true, auto_record: true, last_seen: new Date().toISOString(), current_title: 'Just Chatting with Chat!', current_category: 'Just Chatting' },
        { id: 2, name: 'speedrunner_pro', display_name: 'Speedrunner Pro', twitch_id: '23456', is_live: true, is_recording: false, is_favorite: false, auto_record: true, last_seen: new Date().toISOString(), current_title: 'Ranked Climbing Session', current_category: 'Competitive Gaming' },
        { id: 3, name: 'retro_gamer', display_name: 'Retro Gamer', twitch_id: '34567', is_live: false, is_recording: false, is_favorite: true, auto_record: false, last_seen: null, current_title: null, current_category: null },
        { id: 4, name: 'creative_coder', display_name: 'Creative Coder', twitch_id: '45678', is_live: false, is_recording: false, is_favorite: false, auto_record: true, last_seen: null, current_title: null, current_category: null }
      ]
      streamsStatus.value = []
      notificationsStatus.value = {
        notification_system: { enabled: true, url_configured: false, active_subscriptions: 2, streamers_with_notifications: 2 },
        recent_events: [],
        timestamp: new Date().toISOString()
      }
      lastUpdate.value = new Date()
      return
    }

    await Promise.all([
      fetchSystemStatus(useCache),
      fetchActiveRecordings(useCache),
      fetchStreamersStatus(useCache),
      fetchStreamsStatus(useCache),
      fetchNotificationsStatus(useCache)
    ])
  }
  
  // Force refresh without cache
  const forceRefresh = async (): Promise<void> => {
    const startedGeneration = generation
    if (inFlight.size) await Promise.all(inFlight.values())
    if (startedGeneration === generation) return fetchAllStatus(false)
  }

  // WebSocket event subscriptions via the existing central store.
  const subscribeEvents = () => {
    const onRecordingEnd = (event: RealtimeEvent<string>) => {
      const d = event.data
      if (d && (d.recording_id || d.streamer_id)) {
        if (d.recording_id) {
          activeRecordings.value = activeRecordings.value.filter(rec => rec.id !== d.recording_id)
        } else if (d.streamer_id) {
          activeRecordings.value = activeRecordings.value.filter(rec => rec.streamer_id !== d.streamer_id)
          const si = streamersStatus.value.findIndex(s => s.id === d.streamer_id)
          if (si !== -1) streamersStatus.value[si].is_recording = false
        }
        lastUpdate.value = new Date()
      }
    }
    const findStreamer = (name: string) => {
      return streamersStatus.value.find(
        s => s.name === name || s.display_name === name
      )
    }

    realtimeUnsubs.push(
      realtime.onEvent('active_recordings_update', (event) => {
        if (Array.isArray(event.data)) {
          activeRecordings.value = event.data
          lastUpdate.value = new Date()
        }
      }),

      realtime.onEvent('streamers_update', (event) => {
        if (Array.isArray(event.data)) {
          streamersStatus.value = event.data
          lastUpdate.value = new Date()
        }
      }),

      realtime.onEvent('streams_update', (event) => {
        if (Array.isArray(event.data)) {
          streamsStatus.value = event.data
          lastUpdate.value = new Date()
        }
      }),

      realtime.onEvent('channel.update', (event) => {
        const d = event.data
        if (d && d.streamer_name) {
          const s = findStreamer(d.streamer_name)
          if (s) {
            if (d.title) s.current_title = d.title
            if (d.category_name) s.current_category = d.category_name
            if (d.language) s.language = d.language
            s.last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('stream.online', (event) => {
        const d = event.data
        if (d && d.streamer_name) {
          const s = findStreamer(d.streamer_name)
          if (s) {
            s.is_live = true
            s.last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('stream.offline', (event) => {
        const d = event.data
        if (d && d.streamer_name) {
          const s = findStreamer(d.streamer_name)
          if (s) {
            s.is_live = false
            s.current_title = null
            s.current_category = null
            s.last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('streamer_online', (event) => {
        const d = event.data
        if (d && d.streamer_id) {
          const idx = streamersStatus.value.findIndex(s => s.id === d.streamer_id)
          if (idx !== -1) {
            streamersStatus.value[idx].is_live = true
            streamersStatus.value[idx].current_title = d.title || null
            streamersStatus.value[idx].current_category = d.category || null
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('streamer_offline', (event) => {
        const d = event.data
        if (d && d.streamer_id) {
          const idx = streamersStatus.value.findIndex(s => s.id === d.streamer_id)
          if (idx !== -1) {
            streamersStatus.value[idx].is_live = false
            streamersStatus.value[idx].current_title = null
            streamersStatus.value[idx].current_category = null
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('recording.started', (event) => {
        const d = event.data
        if (d && d.recording_id) {
          const exists = activeRecordings.value.some(rec => rec.id === d.recording_id)
          if (!exists) {
            activeRecordings.value.push({
              id: d.recording_id,
              stream_id: d.stream_id,
              streamer_id: d.streamer_id,
              streamer_name: d.streamer_name || 'Unknown',
              title: d.title || '',
              started_at: d.started_at || new Date().toISOString(),
              file_path: d.file_path || '',
              status: 'recording',
              duration: 0
            })
            const si = streamersStatus.value.findIndex(s => s.id === d.streamer_id)
            if (si !== -1) {
              streamersStatus.value[si].is_recording = true
            }
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('recording.stopped', onRecordingEnd),
      realtime.onEvent('recording.completed', onRecordingEnd),

      realtime.onEvent('notification_event', (event) => {
        const d = event.data
        if (d && notificationsStatus.value) {
          notificationsStatus.value.recent_events.unshift({
            id: Date.now(),
            type: d.type,
            streamer_name: d.streamer_name,
            message: d.message,
            timestamp: new Date().toISOString()
          })
          if (notificationsStatus.value.recent_events.length > 20) {
            notificationsStatus.value.recent_events = notificationsStatus.value.recent_events.slice(0, 20)
          }
          lastUpdate.value = new Date()
        }
      })
    )
  }
  
  function stop() {
    generation++
    realtimeUnsubs.splice(0).forEach(fn => fn())
    stopOwner?.()
    stopOwner = undefined


    inFlight.clear()

    resourceErrors.clear()
    systemStatus.value = null
    activeRecordings.value = []
    streamersStatus.value = []
    streamsStatus.value = []
    notificationsStatus.value = null
    lastUpdate.value = null
  }

  function start() {
    if (stopOwner || !consumers || !enabled || !ownerScope.active) return
    // This watcher belongs to the shared owner, not the first mounting consumer.
    const unwatch = ownerScope.run(() => watch(() => realtime.connectionStatus, (status, _previous, onCleanup) => {
      if (status === 'connected') {
        const timeout = setTimeout(forceRefresh, 1000)
        onCleanup(() => clearTimeout(timeout))
      }
    }))

    // Keep the existing 60s check and >120s emergency threshold, not regular polling.
    const interval = setInterval(() => {
      if (!isOnline.value && (!lastUpdate.value || Date.now() - lastUpdate.value.getTime() > 120000)) {
        void fetchAllStatus(false)
      }
    }, 60000)
    stopOwner = () => {
      unwatch?.()
      clearInterval(interval)
    }
    subscribeEvents()
    void fetchAllStatus(false)
  }

  function setActive(active: boolean) {
    enabled = active
    if (active) start()
    else stop()
  }
  onScopeDispose(stop)

  function retain() {
    consumers++
    start()
  }
  function release() {
    if (--consumers === 0) stop()
  }
  
  // Cache the facade without unwrapping its readonly refs for each consumer.
  return { status: computed(() => ({
    // State
    systemStatus: readonly(systemStatus),
    activeRecordings: readonly(activeRecordings),
    streamersStatus: readonly(streamersStatus),
    streamsStatus: readonly(streamsStatus),
    notificationsStatus: readonly(notificationsStatus),
    isLoading,
    error,
    lastUpdate: readonly(lastUpdate),
    
    // Computed
    isOnline,
    hasActiveRecordings,
    activeRecordingsCount,
    
    // Methods used by current consumers
    fetchActiveRecordings,
    fetchStreamersStatus,
    fetchAllStatus,
    forceRefresh,
    setActive
  })), retain, release }
})

export function useSystemAndRecordingStatus() {
  const store = useSystemStatusStore()
  onMounted(store.retain)
  onUnmounted(store.release)
  return store.status
}
