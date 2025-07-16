/**
 * Enhanced WebSocket composable for real-time data updates
 * Replaces REST API polling for better performance
 */
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useWebSocket } from '@/composables/useWebSocket'

export function useRealtimeData() {
  const { messages, isConnected } = useWebSocket()
  
  // Reactive data stores
  const streamers = ref([])
  const activeRecordings = ref([])
  const backgroundQueue = ref({
    stats: { pending: 0, active: 0, completed: 0, failed: 0 },
    activeTasks: [],
    recentTasks: []
  })
  const streamStatuses = ref(new Map())
  
  // Loading states
  const isLoadingStreamers = ref(false)
  const isLoadingRecordings = ref(false)
  
  // Last update timestamps for debugging
  const lastUpdate = ref({
    streamers: null,
    recordings: null,
    queue: null
  })

  // Process WebSocket messages
  const processMessage = (message: any) => {
    if (!message?.type) return
    
    console.log('📡 RealtimeData: Processing message:', message.type)
    
    switch (message.type) {
      case 'streamer_update':
        updateStreamer(message.data)
        break
        
      case 'stream.online':
      case 'stream.offline':
        updateStreamStatus(message.data)
        break
        
      case 'recording.started':
      case 'recording.stopped':
      case 'recording.update':
        updateRecording(message.data)
        break
        
      case 'queue_stats_update':
        updateQueueStats(message.data)
        break
        
      case 'task_status_update':
        updateTaskStatus(message.data)
        break
        
      case 'task_progress_update':
        updateTaskProgress(message.data)
        break
        
      case 'streamers_list_update':
        if (message.data?.streamers) {
          streamers.value = message.data.streamers
          lastUpdate.value.streamers = new Date().toISOString()
        }
        break
        
      case 'recordings_list_update':
        if (message.data?.recordings) {
          activeRecordings.value = message.data.recordings
          lastUpdate.value.recordings = new Date().toISOString()
        }
        break
    }
  }
  
  const updateStreamer = (streamerData: any) => {
    if (!streamerData?.id) return
    
    const index = streamers.value.findIndex(s => s.id === streamerData.id)
    if (index >= 0) {
      streamers.value[index] = { ...streamers.value[index], ...streamerData }
    } else {
      streamers.value.push(streamerData)
    }
    lastUpdate.value.streamers = new Date().toISOString()
  }
  
  const updateStreamStatus = (streamData: any) => {
    if (!streamData?.streamer_id) return
    
    streamStatuses.value.set(streamData.streamer_id, {
      isLive: streamData.type === 'stream.online',
      streamTitle: streamData.stream_title,
      viewerCount: streamData.viewer_count,
      lastUpdate: new Date().toISOString()
    })
    
    // Update streamer in list
    const streamer = streamers.value.find(s => s.twitch_id === streamData.streamer_id)
    if (streamer) {
      streamer.is_live = streamData.type === 'stream.online'
      streamer.current_stream_title = streamData.stream_title
      streamer.viewer_count = streamData.viewer_count
    }
  }
  
  const updateRecording = (recordingData: any) => {
    if (!recordingData?.id) return
    
    const index = activeRecordings.value.findIndex(r => r.id === recordingData.id)
    
    if (recordingData.status === 'stopped' || recordingData.status === 'completed') {
      // Remove from active recordings
      if (index >= 0) {
        activeRecordings.value.splice(index, 1)
      }
    } else {
      // Add or update active recording
      if (index >= 0) {
        activeRecordings.value[index] = { ...activeRecordings.value[index], ...recordingData }
      } else {
        activeRecordings.value.push(recordingData)
      }
    }
    lastUpdate.value.recordings = new Date().toISOString()
  }
  
  const updateQueueStats = (stats: any) => {
    backgroundQueue.value.stats = { ...backgroundQueue.value.stats, ...stats }
    lastUpdate.value.queue = new Date().toISOString()
  }
  
  const updateTaskStatus = (taskData: any) => {
    if (!taskData?.id) return
    
    // Update active tasks
    const activeIndex = backgroundQueue.value.activeTasks.findIndex(t => t.id === taskData.id)
    if (taskData.status === 'running' || taskData.status === 'pending') {
      if (activeIndex >= 0) {
        backgroundQueue.value.activeTasks[activeIndex] = taskData
      } else {
        backgroundQueue.value.activeTasks.push(taskData)
      }
    } else {
      // Remove from active, add to recent
      if (activeIndex >= 0) {
        backgroundQueue.value.activeTasks.splice(activeIndex, 1)
      }
      
      // Add to recent tasks (keep only last 20)
      backgroundQueue.value.recentTasks.unshift(taskData)
      if (backgroundQueue.value.recentTasks.length > 20) {
        backgroundQueue.value.recentTasks = backgroundQueue.value.recentTasks.slice(0, 20)
      }
    }
  }
  
  const updateTaskProgress = (progressData: any) => {
    if (!progressData?.task_id) return
    
    const task = backgroundQueue.value.activeTasks.find(t => t.id === progressData.task_id)
    if (task) {
      task.progress = progressData.progress
      task.progress_message = progressData.message
    }
  }
  
  // Initial data loading with REST fallback
  const loadInitialData = async () => {
    console.log('📡 RealtimeData: Loading initial data...')
    
    // Load streamers
    isLoadingStreamers.value = true
    try {
      const response = await fetch('/api/streamers')
      if (response.ok) {
        const data = await response.json()
        streamers.value = data.streamers || []
        console.log('📡 Loaded', streamers.value.length, 'streamers via REST')
      }
    } catch (error) {
      console.error('Failed to load initial streamers:', error)
    } finally {
      isLoadingStreamers.value = false
    }
    
    // Load active recordings
    isLoadingRecordings.value = true
    try {
      const response = await fetch('/api/recording/active')
      if (response.ok) {
        const data = await response.json()
        activeRecordings.value = data.recordings || []
        console.log('📡 Loaded', activeRecordings.value.length, 'active recordings via REST')
      }
    } catch (error) {
      console.error('Failed to load initial recordings:', error)
    } finally {
      isLoadingRecordings.value = false
    }
    
    // Load background queue data
    try {
      const [statsResponse, tasksResponse] = await Promise.all([
        fetch('/api/background-queue/stats'),
        fetch('/api/background-queue/active-tasks')
      ])
      
      if (statsResponse.ok) {
        const statsData = await statsResponse.json()
        backgroundQueue.value.stats = statsData.stats || {}
      }
      
      if (tasksResponse.ok) {
        const tasksData = await tasksResponse.json()
        backgroundQueue.value.activeTasks = tasksData.active_tasks || []
      }
      
      console.log('📡 Loaded background queue data via REST')
    } catch (error) {
      console.error('Failed to load initial background queue data:', error)
    }
  }
  
  // Watch for new WebSocket messages
  let previousMessageCount = 0
  const unwatchMessages = computed(() => {
    const newCount = messages.value.length
    if (newCount > previousMessageCount) {
      const newMessages = messages.value.slice(previousMessageCount)
      newMessages.forEach(processMessage)
      previousMessageCount = newCount
    }
    return newCount
  })
  
  // Initialize on mount
  onMounted(() => {
    loadInitialData()
  })
  
  onUnmounted(() => {
    // Cleanup if needed
  })
  
  return {
    // Data
    streamers: computed(() => streamers.value),
    activeRecordings: computed(() => activeRecordings.value),
    backgroundQueue: computed(() => backgroundQueue.value),
    streamStatuses: computed(() => streamStatuses.value),
    
    // Loading states
    isLoadingStreamers: computed(() => isLoadingStreamers.value),
    isLoadingRecordings: computed(() => isLoadingRecordings.value),
    isConnected,
    
    // Debugging
    lastUpdate: computed(() => lastUpdate.value),
    
    // Methods
    loadInitialData,
    
    // Getters
    getStreamerStatus: (streamerId: string) => streamStatuses.value.get(streamerId),
    getActiveTasksCount: computed(() => backgroundQueue.value.activeTasks.length),
    getTotalQueueLength: computed(() => {
      const stats = backgroundQueue.value.stats
      return (stats.pending || 0) + (stats.active || 0)
    })
  }
}
