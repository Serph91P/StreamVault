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

import { ref, computed, onMounted, onUnmounted, watch, readonly } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import { systemApi } from '@/services/api'
import { logDebug, logError } from '@/utils/logger'

// Mock mode check
const USE_MOCK_DATA = import.meta.env.VITE_USE_MOCK_DATA === 'true'

// Configuration constants
const _TIMEOUT_THRESHOLD_MS = 45000 // 45 seconds - fallback to REST if no WebSocket updates

const cacheParams = (useCache: boolean) => useCache ? {} : { t: Date.now() }

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

export function useSystemAndRecordingStatus() {
  // State
  const systemStatus = ref<SystemStatus | null>(null)
  const activeRecordings = ref<ActiveRecording[]>([])
  const streamersStatus = ref<StreamerStatus[]>([])
  const streamsStatus = ref<StreamStatus[]>([])
  const notificationsStatus = ref<NotificationStatus | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastUpdate = ref<Date | null>(null)
  
  // WebSocket integration via central store
  const realtime = useRealtimeStore()
  const realtimeUnsubs: Array<() => void> = []
  
  // Computed properties
  const isOnline = computed(() => realtime.connectionStatus === 'connected')
  const hasActiveRecordings = computed(() => activeRecordings.value.length > 0)
  const activeRecordingsCount = computed(() => activeRecordings.value.length)
  
  // REST API functions for guaranteed current state
  const fetchSystemStatus = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const data = await systemApi.getStatus(cacheParams(useCache))
      systemStatus.value = data.system
      lastUpdate.value = new Date()
      
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      logError('useSystemAndRecordingStatus', 'Failed to fetch system status', err)
    } finally {
      isLoading.value = false
    }
  }
  
  const fetchActiveRecordings = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const data = await systemApi.getActiveRecordingsStatus(cacheParams(useCache))
      activeRecordings.value = data.active_recordings || []
      lastUpdate.value = new Date()
      
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      logError('useSystemAndRecordingStatus', 'Failed to fetch active recordings', err)
    } finally {
      isLoading.value = false
    }
  }
  
  const fetchStreamersStatus = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const data = await systemApi.getStreamersStatus(cacheParams(useCache))
      streamersStatus.value = data.streamers || []
      lastUpdate.value = new Date()
      
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      logError('useSystemAndRecordingStatus', 'Failed to fetch streamers status', err)
    } finally {
      isLoading.value = false
    }
  }
  
  const fetchStreamsStatus = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const data = await systemApi.getStreamsStatus(cacheParams(useCache))
      streamsStatus.value = data.streams || []
      lastUpdate.value = new Date()
      
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      logError('useSystemAndRecordingStatus', 'Failed to fetch streams status', err)
    } finally {
      isLoading.value = false
    }
  }
  
  const fetchNotificationsStatus = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const data = await systemApi.getNotificationsStatus(cacheParams(useCache))
      notificationsStatus.value = data
      lastUpdate.value = new Date()
      
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unknown error'
      logError('useSystemAndRecordingStatus', 'Failed to fetch notifications status', err)
    } finally {
      isLoading.value = false
    }
  }
  
  // Fetch all status data
  const fetchAllStatus = async (useCache = true): Promise<void> => {
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
  const forceRefresh = (): Promise<void> => {
    return fetchAllStatus(false)
  }
  
  // Watch connection status and refresh on reconnect
  watch(() => realtime.connectionStatus, (status, oldStatus) => {
    if (status === 'connected' && oldStatus !== 'connected') {
      // Reconnected - refresh all data to ensure consistency
      setTimeout(() => {
        fetchAllStatus(false) // Force refresh without cache
      }, 1000) // Small delay to allow WebSocket to stabilize
    }
  })

  // WebSocket event subscriptions via central store
  onMounted(() => {
    const markupStreamer = (name: string) => {
      return streamersStatus.value.findIndex(
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
          const idx = markupStreamer(d.streamer_name)
          if (idx !== -1) {
            const s = streamersStatus.value[idx]
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
          const idx = markupStreamer(d.streamer_name)
          if (idx !== -1) {
            streamersStatus.value[idx].is_live = true
            streamersStatus.value[idx].last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
          }
        }
      }),

      realtime.onEvent('stream.offline', (event) => {
        const d = event.data
        if (d && d.streamer_name) {
          const idx = markupStreamer(d.streamer_name)
          if (idx !== -1) {
            const s = streamersStatus.value[idx]
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

      realtime.onEvent('recording.stopped', (event) => {
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
      }),

      realtime.onEvent('recording.completed', (event) => {
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
      }),

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
  })
  
  // Periodic refresh interval (DISABLED - WebSocket provides all updates)
  let refreshInterval: ReturnType<typeof setTimeout> | null = null
  
  const startPeriodicRefresh = (_intervalMs = 30000) => {
    // CRITICAL FIX: Disable polling - WebSocket handles all real-time updates
    // This prevents unnecessary API traffic when WebSocket is working
    logDebug('useSystemAndRecordingStatus', 'Periodic polling DISABLED - using WebSocket-only updates')
    
    // Only use as emergency fallback when WebSocket is completely dead
    if (refreshInterval) {
      clearInterval(refreshInterval)
    }
    
    // Check every 60 seconds if WebSocket is dead for >2 minutes
    refreshInterval = setInterval(() => {
      const timeSinceLastUpdate = lastUpdate.value ? 
        Date.now() - lastUpdate.value.getTime() : 
        Infinity
      
      // EMERGENCY FALLBACK: Only fetch if WebSocket has been dead for 2+ minutes
      const EMERGENCY_THRESHOLD_MS = 120000 // 2 minutes
      if (!isOnline.value && timeSinceLastUpdate > EMERGENCY_THRESHOLD_MS) {
        logError('useSystemAndRecordingStatus', `EMERGENCY FALLBACK: WebSocket dead for ${Math.floor(timeSinceLastUpdate / 1000)}s - using REST API`)
        fetchAllStatus(false) // Force refresh without cache
      }
    }, 60000) // Check every 60 seconds (reduced from 30s)
  }
  
  const stopPeriodicRefresh = () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  }
  
  // Lifecycle
  onMounted(() => {
    // Initial data fetch
    fetchAllStatus(false) // Force initial fetch without cache
    
    // Start periodic refresh as fallback
    startPeriodicRefresh()
  })
  
  onUnmounted(() => {
    realtimeUnsubs.forEach((fn) => fn())
    stopPeriodicRefresh()
  })
  
  return {
    // State
    systemStatus: readonly(systemStatus),
    activeRecordings: readonly(activeRecordings),
    streamersStatus: readonly(streamersStatus),
    streamsStatus: readonly(streamsStatus),
    notificationsStatus: readonly(notificationsStatus),
    isLoading: readonly(isLoading),
    error: readonly(error),
    lastUpdate: readonly(lastUpdate),
    
    // Computed
    isOnline,
    hasActiveRecordings,
    activeRecordingsCount,
    
    // Methods
    fetchSystemStatus,
    fetchActiveRecordings,
    fetchStreamersStatus,
    fetchStreamsStatus,
    fetchNotificationsStatus,
    fetchAllStatus,
    forceRefresh,
    
    // Manual control
    startPeriodicRefresh,
    stopPeriodicRefresh
  }
}
