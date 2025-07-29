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
import { useWebSocket } from './useWebSocket'
import { logDebug, logError, logWebSocket } from '@/utils/logger'

// Configuration constants
const TIMEOUT_THRESHOLD_MS = 45000 // 45 seconds - fallback to REST if no WebSocket updates

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
  
  // WebSocket integration
  const { messages, connectionStatus } = useWebSocket()
  
  // Computed properties
  const isOnline = computed(() => connectionStatus.value === 'connected')
  const hasActiveRecordings = computed(() => activeRecordings.value.length > 0)
  const activeRecordingsCount = computed(() => activeRecordings.value.length)
  
  // REST API functions for guaranteed current state
  const fetchSystemStatus = async (useCache = true): Promise<void> => {
    try {
      isLoading.value = true
      error.value = null
      
      const cacheParam = useCache ? '' : `?t=${Date.now()}`
      const response = await fetch(`/api/status/system${cacheParam}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
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
      
      const cacheParam = useCache ? '' : `?t=${Date.now()}`
      const response = await fetch(`/api/status/active-recordings${cacheParam}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
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
      
      const cacheParam = useCache ? '' : `?t=${Date.now()}`
      const response = await fetch(`/api/status/streamers${cacheParam}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
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
      
      const cacheParam = useCache ? '' : `?t=${Date.now()}`
      const response = await fetch(`/api/status/streams${cacheParam}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
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
      
      const cacheParam = useCache ? '' : `?t=${Date.now()}`
      const response = await fetch(`/api/status/notifications${cacheParam}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const data = await response.json()
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
  
  // WebSocket message processing
  const processWebSocketMessage = (message: any) => {
    logWebSocket('useSystemAndRecordingStatus', 'received', `Processing message type: ${message.type}`, message.data)
    
    switch (message.type) {
      case 'active_recordings_update':
        if (Array.isArray(message.data)) {
          activeRecordings.value = message.data
          lastUpdate.value = new Date()
        }
        break
        
      case 'streamers_update':
        if (Array.isArray(message.data)) {
          streamersStatus.value = message.data
          lastUpdate.value = new Date()
        }
        break
        
      case 'streams_update':
        if (Array.isArray(message.data)) {
          streamsStatus.value = message.data
          lastUpdate.value = new Date()
        }
        break
        
      case 'channel.update':
        // Handle Twitch channel updates (title, category, language changes)
        if (message.data && message.data.streamer_name) {
          const streamerIndex = streamersStatus.value.findIndex(
            s => s.name === message.data.streamer_name || s.name === message.data.username
          )
          if (streamerIndex !== -1) {
            if (message.data.title) {
              streamersStatus.value[streamerIndex].current_title = message.data.title
            }
            if (message.data.category_name) {
              streamersStatus.value[streamerIndex].current_category = message.data.category_name
            }
            if (message.data.language) {
              streamersStatus.value[streamerIndex].language = message.data.language
            }
            streamersStatus.value[streamerIndex].last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
            logDebug('useSystemAndRecordingStatus', `Updated streamer ${message.data.streamer_name} from WebSocket channel.update`)
          }
        }
        break
        
      case 'stream.online':
        // Handle Twitch stream going live
        if (message.data && message.data.streamer_name) {
          const streamerIndex = streamersStatus.value.findIndex(
            s => s.name === message.data.streamer_name || s.name === message.data.username
          )
          if (streamerIndex !== -1) {
            streamersStatus.value[streamerIndex].is_live = true
            streamersStatus.value[streamerIndex].last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
            logDebug('useSystemAndRecordingStatus', `Streamer ${message.data.streamer_name} went LIVE via WebSocket`)
          }
        }
        break
        
      case 'stream.offline':
        // Handle Twitch stream going offline
        if (message.data && message.data.streamer_name) {
          const streamerIndex = streamersStatus.value.findIndex(
            s => s.name === message.data.streamer_name || s.name === message.data.username
          )
          if (streamerIndex !== -1) {
            streamersStatus.value[streamerIndex].is_live = false
            streamersStatus.value[streamerIndex].current_title = null
            streamersStatus.value[streamerIndex].current_category = null
            streamersStatus.value[streamerIndex].last_seen = new Date().toISOString()
            lastUpdate.value = new Date()
            logDebug('useSystemAndRecordingStatus', `Streamer ${message.data.streamer_name} went OFFLINE via WebSocket`)
          }
        }
        break
        
      case 'streamer_online':
        // Update specific streamer status
        if (message.data && message.data.streamer_id) {
          const streamerIndex = streamersStatus.value.findIndex(
            s => s.id === message.data.streamer_id
          )
          if (streamerIndex !== -1) {
            streamersStatus.value[streamerIndex].is_live = true
            streamersStatus.value[streamerIndex].current_title = message.data.title || null
            streamersStatus.value[streamerIndex].current_category = message.data.category || null
            lastUpdate.value = new Date()
          }
        }
        break
        
      case 'streamer_offline':
        // Update specific streamer status
        if (message.data && message.data.streamer_id) {
          const streamerIndex = streamersStatus.value.findIndex(
            s => s.id === message.data.streamer_id
          )
          if (streamerIndex !== -1) {
            streamersStatus.value[streamerIndex].is_live = false
            streamersStatus.value[streamerIndex].current_title = null
            streamersStatus.value[streamerIndex].current_category = null
            lastUpdate.value = new Date()
          }
        }
        break
        
      case 'recording_started':
        // Add to active recordings if not already present
        if (message.data && message.data.recording_id) {
          const existingIndex = activeRecordings.value.findIndex(
            rec => rec.id === message.data.recording_id
          )
          if (existingIndex === -1) {
            const newRecording = {
              id: message.data.recording_id,
              stream_id: message.data.stream_id,
              streamer_id: message.data.streamer_id,
              streamer_name: message.data.streamer_name || 'Unknown',
              title: message.data.title || '',
              started_at: message.data.started_at || new Date().toISOString(),
              file_path: message.data.file_path || '',
              status: 'recording',
              duration: 0
            }
            activeRecordings.value.push(newRecording)
            
            // Also update streamer recording status
            const streamerIndex = streamersStatus.value.findIndex(
              s => s.id === message.data.streamer_id
            )
            if (streamerIndex !== -1) {
              streamersStatus.value[streamerIndex].is_recording = true
            }
            
            lastUpdate.value = new Date()
          }
        }
        break
        
      case 'recording_stopped':
      case 'recording_completed':
        // Remove from active recordings
        if (message.data && (message.data.recording_id || message.data.streamer_id)) {
          if (message.data.recording_id) {
            activeRecordings.value = activeRecordings.value.filter(
              rec => rec.id !== message.data.recording_id
            )
          } else if (message.data.streamer_id) {
            activeRecordings.value = activeRecordings.value.filter(
              rec => rec.streamer_id !== message.data.streamer_id
            )
            
            // Update streamer recording status
            const streamerIndex = streamersStatus.value.findIndex(
              s => s.id === message.data.streamer_id
            )
            if (streamerIndex !== -1) {
              streamersStatus.value[streamerIndex].is_recording = false
            }
          }
          lastUpdate.value = new Date()
        }
        break
        
      case 'notification_event':
        // Add to recent notifications
        if (message.data && notificationsStatus.value) {
          notificationsStatus.value.recent_events.unshift({
            id: Date.now(), // temporary ID
            type: message.data.type,
            streamer_name: message.data.streamer_name,
            message: message.data.message,
            timestamp: new Date().toISOString()
          })
          
          // Keep only last 20 events
          if (notificationsStatus.value.recent_events.length > 20) {
            notificationsStatus.value.recent_events = notificationsStatus.value.recent_events.slice(0, 20)
          }
          
          lastUpdate.value = new Date()
        }
        break
    }
  }
  
  // Watch for WebSocket messages
  watch(messages, (newMessages) => {
    if (newMessages.length > 0) {
      const latestMessage = newMessages[newMessages.length - 1]
<<<<<<< HEAD
      logWebSocket('useSystemAndRecordingStatus', 'received', 'New WebSocket message', latestMessage)
=======
      if (process.env.NODE_ENV === 'development') {
        console.debug('🔍 [useSystemAndRecordingStatus] Received WebSocket message:', latestMessage)
      }
>>>>>>> d109921a00a8e031e2203d1200aeb343c0845021
      processWebSocketMessage(latestMessage)
    }
  }, { deep: true })
  
  // Watch connection status and refresh on reconnect
  watch(connectionStatus, (status, oldStatus) => {
    if (status === 'connected' && oldStatus !== 'connected') {
      // Reconnected - refresh all data to ensure consistency
      setTimeout(() => {
        fetchAllStatus(false) // Force refresh without cache
      }, 1000) // Small delay to allow WebSocket to stabilize
    }
  })
  
  // Periodic refresh interval (fallback when WebSocket updates aren't working)
  let refreshInterval: NodeJS.Timeout | null = null
  
  const startPeriodicRefresh = (intervalMs = 30000) => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
    }
    
    refreshInterval = setInterval(() => {
      // Only refresh if WebSocket is disconnected or no recent updates
      const timeSinceLastUpdate = lastUpdate.value ? 
        Date.now() - lastUpdate.value.getTime() : 
        Infinity
      
      if (!isOnline.value || timeSinceLastUpdate > TIMEOUT_THRESHOLD_MS) {
        fetchAllStatus(true) // Use cache for periodic refresh
      }
    }, intervalMs)
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
