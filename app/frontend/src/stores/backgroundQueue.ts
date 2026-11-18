import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import { backgroundQueueApi } from '@/services/api'
import { logError } from '@/utils/logger'

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
  const dataAvailable = ref(false)

  const hasActiveTasks = computed(() => activeTasks.value.length > 0)
  const totalProgress = computed(() =>
    activeTasks.value.reduce((sum, task) => sum + task.progress, 0) / (activeTasks.value.length || 1)
  )
  const hasError = computed(() => error.value !== null)

  let realtimeBindingCount = 0
  let realtimeUnsubs: Array<() => void> = []
  const realtime = useRealtimeStore()
  let revision = 0
  let pending: Promise<void> | undefined
  let disposed = false

  watch(() => realtime.snapshotRevision, async () => {
    revision++
    dataAvailable.value = false
    if (pending) await pending
    if (!disposed && realtimeBindingCount && !dataAvailable.value) void forceRefreshFromAPI()
  }, { flush: 'sync' })

  onScopeDispose(() => {
    disposed = true
    revision++
    realtimeUnsubs.splice(0).forEach(fn => fn())
  })

  function setQueueStats(stats: Partial<BackgroundQueueStats>): void {
    revision++
    queueStats.value = {
      ...queueStats.value,
      ...stats
    }
  }

  function setActiveTasks(tasks: BackgroundQueueTask[]): void {
    revision++
    activeTasks.value = Array.isArray(tasks) ? tasks : []
  }

  function setRecentTasks(tasks: BackgroundQueueTask[]): void {
    revision++
    recentTasks.value = Array.isArray(tasks) ? tasks : []
  }

  function applyTaskStatusUpdate(taskData: BackgroundQueueTask): void {
    revision++
    if (import.meta.env.DEV) console.debug('useBackgroundQueue', `Task status update for ${taskData.id}: ${taskData.status}`)
    const existingIndex = activeTasks.value.findIndex((task) => task.id === taskData.id)
    if (existingIndex >= 0) {
      activeTasks.value[existingIndex] = taskData
    } else if (isActiveTaskStatus(taskData.status)) {
      activeTasks.value.push(taskData)
    }

    if (taskData.status === 'completed' || taskData.status === 'failed') {
      activeTasks.value = activeTasks.value.filter((task) => task.id !== taskData.id)
      recentTasks.value = recentTasks.value.filter((task) => task.id !== taskData.id)
      recentTasks.value.unshift(taskData)
      if (recentTasks.value.length > 50) {
        recentTasks.value = recentTasks.value.slice(0, 50)
      }
    }
  }

  function applyTaskProgressUpdate(taskId: string, progress: number): void {
    revision++
    if (import.meta.env.DEV) console.debug('useBackgroundQueue', `Progress update for ${taskId}: ${progress}%`)
    const task = activeTasks.value.find((task) => task.id === taskId)
    if (task) {
      task.progress = progress
    }
  }

  function bindRealtime(): () => void {
    realtimeBindingCount += 1
    if (realtimeBindingCount === 1) {
      realtimeUnsubs = [
        realtime.onEvent('background_queue_update', (event) => {
          if (import.meta.env.DEV) console.debug('useBackgroundQueue', 'Updating background queue from WebSocket data')
          if (event.data.stats) {
            setQueueStats(event.data.stats)
          }
          if (Array.isArray(event.data.active_tasks)) {
            setActiveTasks(event.data.active_tasks)
          }
          if (Array.isArray(event.data.recent_tasks)) {
            setRecentTasks(event.data.recent_tasks)
          }
          error.value = null
          if (event.data.stats && Array.isArray(event.data.active_tasks) && Array.isArray(event.data.recent_tasks)) {
            dataAvailable.value = true
          }
        }),
        realtime.onEvent('queue_stats_update', (event) => {
          setQueueStats(event.data)
          if (import.meta.env.DEV) console.debug('useBackgroundQueue', 'Updated queue stats only')
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

    let bound = true
    return () => {
      if (!bound) return
      bound = false
      realtimeBindingCount = Math.max(0, realtimeBindingCount - 1)
      if (realtimeBindingCount === 0) {
        revision++
        dataAvailable.value = false
        realtimeUnsubs.forEach((fn) => fn())
        realtimeUnsubs = []
      }
    }
  }

  function forceRefreshFromAPI(): Promise<void> {
    if (disposed) return Promise.resolve()
    if (pending) return pending
    const started = revision
    if (import.meta.env.DEV) console.debug('useBackgroundQueue', 'FORCE REFRESH: Using API as fallback')
    isLoading.value = true
    error.value = null

    pending = (async () => {
      try {
        const [stats, active, recent] = await Promise.all([
          backgroundQueueApi.getStats(),
          backgroundQueueApi.getActiveTasks(),
          backgroundQueueApi.getRecentTasks()
        ])

        if (disposed || started !== revision) return
        setQueueStats(stats)
        setActiveTasks(active)
        setRecentTasks(recent)
        dataAvailable.value = true
        if (import.meta.env.DEV) console.debug('useBackgroundQueue', 'FORCE REFRESH: API data loaded as fallback')
      } catch (err) {
        if (disposed || started !== revision) return
        error.value = err instanceof Error ? err.message : String(err)
        logError('useBackgroundQueue', 'FORCE REFRESH: API fallback failed', err)
      } finally {
        isLoading.value = false
        pending = undefined
      }
    })()
    return pending
  }

  async function cancelStreamTasks(streamId: number): Promise<void> {
    try {
      error.value = null
      await backgroundQueueApi.cancelStreamTasks(streamId)
      if (import.meta.env.DEV) console.debug('useBackgroundQueue', 'Stream tasks cancelled, waiting for WebSocket update')
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      logError('useBackgroundQueue', 'Failed to cancel stream tasks', err)
    }
  }

  async function hydrateWhenDisconnected(): Promise<void> {
    // The global socket may have sent its snapshot before this monitor mounted.
    // Fetch once when no snapshot exists, irrespective of connection status.
    if (!dataAvailable.value && !isLoading.value) {
      await forceRefreshFromAPI()
    }
  }

  return {
    activeTasks,
    recentTasks,
    queueStats,
    isLoading,
    error,
    dataAvailable,
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
