import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import { backgroundQueueApi } from '@/services/api'
import { logDebug, logError } from '@/utils/logger'

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

  const realtime = useRealtimeStore()
  const realtimeUnsubs: Array<() => void> = []
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
      const [stats, active, recent] = await Promise.all([
        backgroundQueueApi.getStats(),
        backgroundQueueApi.getActiveTasks(),
        backgroundQueueApi.getRecentTasks()
      ])

      queueStats.value = stats
      activeTasks.value = Array.isArray(active) ? active : []
      recentTasks.value = Array.isArray(recent) ? recent : []
      
      logDebug('useBackgroundQueue', 'FORCE REFRESH: API data loaded as fallback')
    } catch (error) {
      logError('useBackgroundQueue', 'FORCE REFRESH: API fallback failed', error)
    } finally {
      isLoading.value = false
    }
  }

  const cancelStreamTasks = async (streamId: number) => {
    try {
      await backgroundQueueApi.cancelStreamTasks(streamId)
      logDebug('useBackgroundQueue', 'Stream tasks cancelled - waiting for WebSocket update')
      // Don't manually refresh - let WebSocket handle the update
    } catch (error) {
      logError('useBackgroundQueue', 'Failed to cancel stream tasks', error)
    }
  }

  // WebSocket message handling via central store subscriptions
  onMounted(() => {
    realtimeUnsubs.push(
      realtime.onEvent('background_queue_update', (event) => {
        logDebug('useBackgroundQueue', 'Updating background queue from WebSocket data')
        if (event.data.stats) {
          Object.assign(queueStats.value, event.data.stats)
        }
        if (Array.isArray(event.data.active_tasks)) {
          activeTasks.value = event.data.active_tasks
        }
        if (Array.isArray(event.data.recent_tasks)) {
          recentTasks.value = event.data.recent_tasks
        }
      }),

      realtime.onEvent('queue_stats_update', (event) => {
        Object.assign(queueStats.value, event.data)
        logDebug('useBackgroundQueue', 'Updated queue stats only')
      }),

      realtime.onEvent('task_status_update', (event) => {
        const taskData = event.data
        logDebug('useBackgroundQueue', `Task status update for ${taskData.id}: ${taskData.status}`)
        const existingIndex = activeTasks.value.findIndex(t => t.id === taskData.id)
        if (existingIndex >= 0) {
          activeTasks.value[existingIndex] = taskData
        } else if (taskData.status === 'running' || taskData.status === 'pending') {
          activeTasks.value.push(taskData)
        }
        if (taskData.status === 'completed' || taskData.status === 'failed') {
          activeTasks.value = activeTasks.value.filter(t => t.id !== taskData.id)
          recentTasks.value.unshift(taskData)
          if (recentTasks.value.length > 50) {
            recentTasks.value = recentTasks.value.slice(0, 50)
          }
        }
      }),

      realtime.onEvent('task_progress_update', (event) => {
        const { task_id, progress } = event.data
        logDebug('useBackgroundQueue', `Progress update for ${task_id}: ${progress}%`)
        const task = activeTasks.value.find(t => t.id === task_id)
        if (task) {
          task.progress = progress
        }
      })
    )
  })

  // Lifecycle
  onMounted(async () => {
    // WEBSOCKET-ONLY: No initial API calls - wait for WebSocket data
    logDebug('useBackgroundQueue', 'Background Queue: Waiting for WebSocket data (no API calls)')
    
    // If WebSocket is not connected yet, use fallback once
    if (realtime.connectionStatus !== 'connected') {
      logDebug('useBackgroundQueue', 'WebSocket not connected yet - using API fallback for initial load')
      await forceRefreshFromAPI()
    }
  })

  onUnmounted(() => {
    realtimeUnsubs.forEach((fn) => fn())
  })

  return {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading,
    connectionStatus: realtime.connectionStatus,
    // Methods
    forceRefreshFromAPI,
    cancelStreamTasks
  }
}
