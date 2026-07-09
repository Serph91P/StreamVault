import { onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRealtimeStore } from '@/stores/realtime'
import { useBackgroundQueueStore } from '@/stores/backgroundQueue'

export function useBackgroundQueue() {
  const store = useBackgroundQueueStore()
  const realtime = useRealtimeStore()
  const {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading
  } = storeToRefs(store)

  let unbindRealtime: (() => void) | null = null

  onMounted(async () => {
    unbindRealtime = store.bindRealtime()
    await store.hydrateWhenDisconnected()
  })

  onUnmounted(() => {
    unbindRealtime?.()
  })

  return {
    activeTasks,
    recentTasks,
    queueStats,
    hasActiveTasks,
    totalProgress,
    isLoading,
    connectionStatus: realtime.connectionStatus,
    forceRefreshFromAPI: store.forceRefreshFromAPI,
    cancelStreamTasks: store.cancelStreamTasks
  }
}