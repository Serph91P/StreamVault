import { onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRealtimeStore } from '@/stores/realtime'
import { useBackgroundQueueStore } from '@/stores/backgroundQueue'

export function useBackgroundQueue() {
  const store = useBackgroundQueueStore()
  const { connectionStatus } = storeToRefs(useRealtimeStore())
  const {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading,
    dataAvailable,
    error
  } = storeToRefs(store)

  let unbindRealtime: (() => void) | undefined

  onMounted(() => {
    unbindRealtime = store.bindRealtime()
    return store.hydrateWhenDisconnected()
  })

  onUnmounted(() => unbindRealtime?.())

  return {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading,
    connectionStatus,
    dataAvailable,
    error,
    forceRefreshFromAPI: store.forceRefreshFromAPI,
    cancelStreamTasks: store.cancelStreamTasks
  }
}