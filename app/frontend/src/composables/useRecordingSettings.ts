import { onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRecordingStore } from '@/stores/recordings'

export function useRecordingSettings() {
  const store = useRecordingStore()
  const {
    settings,
    streamerSettings,
    activeRecordings,
    isLoading,
    error
  } = storeToRefs(store)

  let unbindRealtime: (() => void) | null = null

  onMounted(() => {
    unbindRealtime = store.bindRealtime()
  })

  onUnmounted(() => {
    unbindRealtime?.()
  })

  return {
    settings,
    streamerSettings,
    activeRecordings,
    isLoading,
    error,
    fetchSettings: store.fetchSettings,
    updateSettings: store.updateSettings,
    fetchStreamerSettings: store.fetchStreamerSettings,
    updateStreamerSettings: store.updateStreamerSettings,
    fetchActiveRecordings: store.fetchActiveRecordings,
    stopRecording: store.stopRecording,
    cleanupOldRecordings: store.cleanupOldRecordings,
    getDefaultCleanupPolicy: store.getDefaultCleanupPolicy,
    updateCleanupPolicy: store.updateCleanupPolicy,
    updateStreamerCleanupPolicy: store.updateStreamerCleanupPolicy,
    runCustomCleanup: store.runCustomCleanup,
    getStreamerStorageUsage: store.getStreamerStorageUsage,
    getAvailableCategories: store.getAvailableCategories
  }
}