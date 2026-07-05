import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import { backgroundQueueApi } from '@/services/api'
import { logDebug, logError } from '@/utils/logger'

export interface BackgroundQueueTask {
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
    [key: string]: unknown
  }
}

export interface BackgroundQueueStats {
  total_tasks: number
  completed_tasks: number
  failed_tasks: number
  retried_tasks: number
  pending_tasks: number
  active_tasks: number
  workers: number
  is_running: boolean
}

const defaultStats = (): BackgroundQueueStats => ({
  total_tasks: 0,
  completed_tasks: 0,
  failed_tasks: 0,
  retried_tasks: 0,
  pending_tasks: 0,
  active_tasks: 0,
  workers: 0,
  is_running: false
})

function isActiveTaskStatus(status: BackgroundQueueTask['status']): boolean {
  return status === 'running' || status === 'pending' || status === 'retrying'
}

export const useBackgroundQueueStore = defineStore('backgroundQueue', () => {
  const activeTasks = ref<BackgroundQueueTask[]>([])
  const recentTasks = ref<BackgroundQueueTask[]>([])
  const queueStats = ref<BackgroundQueueStats>(defaultStats())
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const hasActiveTasks = computed(() => activeTasks.value.length > 0)
  const totalProgress = computed(() => {
    if (activeTasks.value.length === 0) return 0
    const progress = activeTasks.value.reduce((sum, task) => sum + task.progress, 0)
    return progress / activeTasks.value.length
  })
  const hasError = computed(() => error.value !== null)

  let realtimeBindingCount = 0
  let realtimeUnsubs: Array<() => void> = []

  function setQueueStats(stats: Partial<BackgroundQueueStats>): void {
    queueStats.value = {
      ...queueStats.value,
      ...stats
    }
  }

  function setActiveTasks(tasks: BackgroundQueueTask[]): void {
    activeTasks.value = Array.isArray(tasks) ? tasks : []
  }

  function setRecentTasks(tasks: BackgroundQueueTask[]): void {
    recentTasks.value = Array.isArray(tasks) ? tasks : []
  }

  function applyTaskStatusUpdate(taskData: BackgroundQueueTask): void {
    logDebug('useBackgroundQueue', `Task status update for ${taskData.id}: ${taskData.status}`)
    const existingIndex = activeTasks.value.findIndex((task) => task.id === taskData.id)
    if (existingIndex >= 0) {
      activeTasks.value[existingIndex] = taskData
    } else if (isActiveTaskStatus(taskData.status)) {
      activeTasks.value.push(taskData)
    }

    if (taskData.status === 'completed' || taskData.status === 'failed') {
      activeTasks.value = activeTasks.value.filter((task) => task.id !== taskData.id)
      recentTasks.value.unshift(taskData)
      if (recentTasks.value.length > 50) {
        recentTasks.value = recentTasks.value.slice(0, 50)
      }
    }
  }

  function applyTaskProgressUpdate(taskId: string, progress: number): void {
    logDebug('useBackgroundQueue', `Progress update for ${taskId}: ${progress}%`)
    const task = activeTasks.value.find((task) => task.id === taskId)
    if (task) {
      task.progress = progress
    }
  }

  function bindRealtime(): () => void {
    realtimeBindingCount += 1
    if (realtimeBindingCount === 1) {
      const realtime = useRealtimeStore()
      realtimeUnsubs = [
        realtime.onEvent('background_queue_update', (event) => {
          logDebug('useBackgroundQueue', 'Updating background queue from WebSocket data')
          if (event.data.stats) {
            setQueueStats(event.data.stats)
          }
          if (Array.isArray(event.data.active_tasks)) {
            setActiveTasks(event.data.active_tasks)
          }
          if (Array.isArray(event.data.recent_tasks)) {
            setRecentTasks(event.data.recent_tasks)
          }
        }),
        realtime.onEvent('queue_stats_update', (event) => {
          setQueueStats(event.data)
          logDebug('useBackgroundQueue', 'Updated queue stats only')
        }),
        realtime.onEvent('task_status_update', (event) => {
          applyTaskStatusUpdate(event.data)
        }),
        realtime.onEvent('task_progress_update', (event) => {
          const { task_id, progress } = event.data
          applyTaskProgressUpdate(task_id, progress)
        })
      ]
    }

    return () => {
      realtimeBindingCount = Math.max(0, realtimeBindingCount - 1)
      if (realtimeBindingCount === 0) {
        realtimeUnsubs.forEach((fn) => fn())
        realtimeUnsubs = []
      }
    }
  }

  async function forceRefreshFromAPI(): Promise<void> {
    logDebug('useBackgroundQueue', 'FORCE REFRESH: Using API as fallback')
    isLoading.value = true
    error.value = null

    try {
      const [stats, active, recent] = await Promise.all([
        backgroundQueueApi.getStats(),
        backgroundQueueApi.getActiveTasks(),
        backgroundQueueApi.getRecentTasks()
      ])

      setQueueStats(stats)
      setActiveTasks(active)
      setRecentTasks(recent)
      logDebug('useBackgroundQueue', 'FORCE REFRESH: API data loaded as fallback')
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      logError('useBackgroundQueue', 'FORCE REFRESH: API fallback failed', err)
    } finally {
      isLoading.value = false
    }
  }

  async function cancelStreamTasks(streamId: number): Promise<void> {
    try {
      error.value = null
      await backgroundQueueApi.cancelStreamTasks(streamId)
      logDebug('useBackgroundQueue', 'Stream tasks cancelled, waiting for WebSocket update')
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      logError('useBackgroundQueue', 'Failed to cancel stream tasks', err)
    }
  }

  async function hydrateWhenDisconnected(): Promise<void> {
    const realtime = useRealtimeStore()
    logDebug('useBackgroundQueue', 'Background Queue: Waiting for WebSocket data')
    if (realtime.connectionStatus !== 'connected') {
      logDebug('useBackgroundQueue', 'WebSocket not connected yet, using API fallback for initial load')
      await forceRefreshFromAPI()
    }
  }

  return {
    activeTasks,
    recentTasks,
    queueStats,
    isLoading,
    error,
    hasActiveTasks,
    totalProgress,
    hasError,
    setQueueStats,
    setActiveTasks,
    setRecentTasks,
    applyTaskStatusUpdate,
    applyTaskProgressUpdate,
    bindRealtime,
    forceRefreshFromAPI,
    cancelStreamTasks,
    hydrateWhenDisconnected
  }
})
