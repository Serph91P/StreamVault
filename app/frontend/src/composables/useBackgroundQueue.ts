import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from './useWebSocket'
import { logDebug, logError, logWebSocket } from '@/utils/logger'

interface Task {
  id: string
  task_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'retrying'
  progress: number
  created_at: string
  started_at?: string
  completed_at?: string
  error_message?: string
  retry_count: number
  payload: {
    streamer_name: string
    stream_id: number
    recording_id: number
    [key: string]: any
  }
}

interface QueueStats {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  retried_tasks: number
  pending_tasks: number
  active_tasks: number
  workers: number
  is_running: boolean
}

export function useBackgroundQueue() {
  const activeTasks = ref<Task[]>([])
  const recentTasks = ref<Task[]>([])
  const queueStats = ref<QueueStats>({
    total_tasks: 0,
    completed_tasks: 0,
    failed_tasks: 0,
    retried_tasks: 0,
    pending_tasks: 0,
    active_tasks: 0,
    workers: 0,
    is_running: false
  })

  const { messages, connectionStatus } = useWebSocket()
  const isLoading = ref(false)

  // Computed properties
  const hasActiveTasks = computed(() => activeTasks.value.length > 0)
  
  const totalProgress = computed(() => {
    if (activeTasks.value.length === 0) return 0
    const totalProgress = activeTasks.value.reduce((sum, task) => sum + task.progress, 0)
    return totalProgress / activeTasks.value.length
  })

  // Only keep one API method for manual refresh when WebSocket fails
  const forceRefreshFromAPI = async () => {
    logDebug('useBackgroundQueue', 'FORCE REFRESH: Using API as fallback (WebSocket might be down)')
    isLoading.value = true
    
    try {
      const [statsRes, activeRes, recentRes] = await Promise.all([
        fetch('/api/background-queue/stats'),
        fetch('/api/background-queue/active-tasks'),
        fetch('/api/background-queue/recent-tasks')
      ])

      if (statsRes.ok) {
        const stats = await statsRes.json()
        queueStats.value = stats
      }
      
      if (activeRes.ok) {
        const tasks = await activeRes.json()
        activeTasks.value = Array.isArray(tasks) ? tasks : []
      }
      
      if (recentRes.ok) {
        const tasks = await recentRes.json()
        recentTasks.value = Array.isArray(tasks) ? tasks : []
      }
      
      logDebug('useBackgroundQueue', 'FORCE REFRESH: API data loaded as fallback')
    } catch (error) {
      logError('useBackgroundQueue', 'FORCE REFRESH: API fallback failed', error)
    } finally {
      isLoading.value = false
    }
  }

  const cancelStreamTasks = async (streamId: number) => {
    try {
      const response = await fetch(`/api/background-queue/cancel-stream/${streamId}`, {
        method: 'POST'
      })
      if (response.ok) {
        logDebug('useBackgroundQueue', 'Stream tasks cancelled - waiting for WebSocket update')
        // Don't manually refresh - let WebSocket handle the update
      }
    } catch (error) {
      logError('useBackgroundQueue', 'Failed to cancel stream tasks', error)
    }
  }

  // WebSocket message handling - SIMPLIFIED: Only one handler
  watch(messages, async (newMessages) => {
    if (newMessages.length === 0) return
    
    const latestMessage = newMessages[newMessages.length - 1]
    logWebSocket('useBackgroundQueue', 'received', `WebSocket message: ${latestMessage.type}`)
    
    // Handle queue-related WebSocket messages
    if (latestMessage.type === 'background_queue_update') {
      // PRIORITY: WebSocket data overwrites everything
      logDebug('useBackgroundQueue', 'Updating background queue from WebSocket data')
      
      if (latestMessage.data.stats) {
        Object.assign(queueStats.value, latestMessage.data.stats)
        logDebug('useBackgroundQueue', 'Updated queue stats')
      }
      if (Array.isArray(latestMessage.data.active_tasks)) {
        activeTasks.value = latestMessage.data.active_tasks
        logDebug('useBackgroundQueue', `Set ${latestMessage.data.active_tasks.length} active tasks`)
      }
      if (Array.isArray(latestMessage.data.recent_tasks)) {
        recentTasks.value = latestMessage.data.recent_tasks
        logDebug('useBackgroundQueue', `Set ${latestMessage.data.recent_tasks.length} recent tasks`)
      }
      
    } else if (latestMessage.type === 'queue_stats_update') {
      Object.assign(queueStats.value, latestMessage.data)
      logDebug('useBackgroundQueue', 'Updated queue stats only')
      
    } else if (latestMessage.type === 'task_status_update') {
      const taskData = latestMessage.data
      logDebug('useBackgroundQueue', `Task status update for ${taskData.id}: ${taskData.status}`)
      
      // Update or add task in activeTasks
      const existingIndex = activeTasks.value.findIndex(t => t.id === taskData.id)
      if (existingIndex >= 0) {
        activeTasks.value[existingIndex] = taskData
      } else if (taskData.status === 'running' || taskData.status === 'pending') {
        activeTasks.value.push(taskData)
      }
      
      // Remove completed tasks from active list
      if (taskData.status === 'completed' || taskData.status === 'failed') {
        activeTasks.value = activeTasks.value.filter(t => t.id !== taskData.id)
        // Add to recent tasks
        recentTasks.value.unshift(taskData)
        // Keep only last 50 recent tasks
        if (recentTasks.value.length > 50) {
          recentTasks.value = recentTasks.value.slice(0, 50)
        }
      }
      
    } else if (latestMessage.type === 'task_progress_update') {
      const { task_id, progress } = latestMessage.data
      logDebug('useBackgroundQueue', `Progress update for ${task_id}: ${progress}%`)
      
      // Update progress for the specific task
      const task = activeTasks.value.find(t => t.id === task_id)
      if (task) {
        task.progress = progress
      }
    }
  })

  // Lifecycle
  onMounted(async () => {
    // WEBSOCKET-ONLY: No initial API calls - wait for WebSocket data
    logDebug('useBackgroundQueue', 'Background Queue: Waiting for WebSocket data (no API calls)')
    
    // If WebSocket is not connected yet, use fallback once
    if (connectionStatus.value !== 'connected') {
      logDebug('useBackgroundQueue', 'WebSocket not connected yet - using API fallback for initial load')
      await forceRefreshFromAPI()
    }
  })

  onUnmounted(() => {
    // Cleanup if needed
  })

  return {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading,
    connectionStatus,
    // Methods
    forceRefreshFromAPI,
    cancelStreamTasks
  }
}
