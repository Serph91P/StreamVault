import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useWebSocket } from './useWebSocket'

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

  const { messages } = useWebSocket()

  // Computed properties
  const hasActiveTasks = computed(() => activeTasks.value.length > 0)
  
  const totalProgress = computed(() => {
    if (activeTasks.value.length === 0) return 0
    const totalProgress = activeTasks.value.reduce((sum, task) => sum + task.progress, 0)
    return totalProgress / activeTasks.value.length
  })

  // API calls
  const fetchQueueStats = async () => {
    try {
      const response = await fetch('/api/background-queue/stats')
      if (response.ok) {
        const stats = await response.json()
        queueStats.value = stats
      }
    } catch (error) {
      console.error('Failed to fetch queue stats:', error)
    }
  }

  const fetchActiveTasks = async () => {
    try {
      const response = await fetch('/api/background-queue/active-tasks')
      if (response.ok) {
        const tasks = await response.json()
        activeTasks.value = tasks
      }
    } catch (error) {
      console.error('Failed to fetch active tasks:', error)
    }
  }

  const fetchRecentTasks = async () => {
    try {
      const response = await fetch('/api/background-queue/recent-tasks')
      if (response.ok) {
        const tasks = await response.json()
        recentTasks.value = tasks
      }
    } catch (error) {
      console.error('Failed to fetch recent tasks:', error)
    }
  }

  const fetchTaskStatus = async (taskId: string) => {
    try {
      const response = await fetch(`/api/background-queue/task/${taskId}`)
      if (response.ok) {
        return await response.json()
      }
    } catch (error) {
      console.error('Failed to fetch task status:', error)
    }
    return null
  }

  const cancelStreamTasks = async (streamId: number) => {
    try {
      const response = await fetch(`/api/background-queue/cancel-stream/${streamId}`, {
        method: 'POST'
      })
      if (response.ok) {
        const result = await response.json()

        // Refresh data
        await fetchActiveTasks()
        await fetchQueueStats()
      }
    } catch (error) {
      console.error('Failed to cancel stream tasks:', error)
    }
  }

  // WebSocket message handling
  const processWebSocketMessage = (message: any) => {
    if (message.type === 'queue_stats_update') {
      queueStats.value = message.data
    } else if (message.type === 'task_status_update') {
      const taskUpdate = message.data
      
      // Update active tasks
      const activeIndex = activeTasks.value.findIndex(t => t.id === taskUpdate.id)
      if (activeIndex !== -1) {
        if (taskUpdate.status === 'completed' || taskUpdate.status === 'failed') {
          // Move to recent tasks
          recentTasks.value.unshift(activeTasks.value[activeIndex])
          activeTasks.value.splice(activeIndex, 1)
          
          // Keep only last 50 recent tasks
          if (recentTasks.value.length > 50) {
            recentTasks.value = recentTasks.value.slice(0, 50)
          }
        } else {
          // Update existing task
          activeTasks.value[activeIndex] = { ...activeTasks.value[activeIndex], ...taskUpdate }
        }
      } else if (taskUpdate.status === 'running' || taskUpdate.status === 'pending') {
        // Add new active task
        activeTasks.value.push(taskUpdate)
      }
    } else if (message.type === 'task_progress_update') {
      const progressUpdate = message.data
      const activeIndex = activeTasks.value.findIndex(t => t.id === progressUpdate.task_id)
      if (activeIndex !== -1) {
        activeTasks.value[activeIndex].progress = progressUpdate.progress
      }
    }
  }

  // Watch for WebSocket messages
  let websocketWatcher: any = null

  const startWatching = () => {
    if (websocketWatcher) return
    
    // Watch for new messages in the WebSocket messages array
    websocketWatcher = watch(messages, (newMessages) => {
      if (newMessages.length > 0) {
        // Process the latest message
        const latestMessage = newMessages[newMessages.length - 1]
        processWebSocketMessage(latestMessage)
      }
    }, { deep: true })
  }

  const stopWatching = () => {
    if (websocketWatcher) {
      websocketWatcher()
      websocketWatcher = null
    }
  }

  // Watch for WebSocket messages
  watch(messages, (newMessages) => {
    if (newMessages.length === 0) return
    
    const latestMessage = newMessages[newMessages.length - 1]
    
    // Handle queue-related WebSocket messages
    if (latestMessage.type === 'queue_stats_update') {
      Object.assign(queueStats.value, latestMessage.data)
    } else if (latestMessage.type === 'task_status_update') {
      const taskData = latestMessage.data
      
      // Update or add task in activeTasks
      const existingIndex = activeTasks.value.findIndex(t => t.id === taskData.id)
      if (existingIndex >= 0) {
        activeTasks.value[existingIndex] = taskData
      } else if (taskData.status === 'active') {
        activeTasks.value.push(taskData)
      }
      
      // Remove completed tasks from active list
      if (taskData.status === 'completed' || taskData.status === 'failed') {
        activeTasks.value = activeTasks.value.filter(t => t.id !== taskData.id)
      }
    } else if (latestMessage.type === 'task_progress_update') {
      const { task_id, progress } = latestMessage.data
      
      // Update progress for the specific task
      const task = activeTasks.value.find(t => t.id === task_id)
      if (task) {
        task.progress = progress
      }
    }
  })

  // Lifecycle
  onMounted(async () => {
    // Initial data load
    await Promise.all([
      fetchQueueStats(),
      fetchActiveTasks(),
      fetchRecentTasks()
    ])
    
    // Start watching for updates (WebSocket only)
    startWatching()
  })

  onUnmounted(() => {
    stopWatching()
  })

  return {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    fetchQueueStats,
    fetchActiveTasks,
    fetchRecentTasks,
    fetchTaskStatus,
    cancelStreamTasks,
    processWebSocketMessage
  }
}
