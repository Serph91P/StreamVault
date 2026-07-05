import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useRealtimeStore } from '@/stores/realtime'
import {
  cleanupRecordings,
  fetchActiveRecordings as fetchActiveRecordingsService,
  fetchAvailableCategories,
  fetchRecordingSettings,
  fetchStreamerRecordingSettings,
  fetchStreamerStorageUsage,
  runCleanup,
  saveRecordingSettings,
  saveStreamerCleanupPolicy,
  saveStreamerRecordingSettings,
  stopStreamerRecording,
  type CategoryOption,
  type CleanupResult,
  type StreamerStorageUsage
} from '@/services/recording'
import type {
  ActiveRecording,
  CleanupPolicy,
  RecordingSettings,
  StreamerRecordingSettings
} from '@/types/recording'
import { CleanupPolicyType } from '@/types/recording'
import type { RealtimeEvent } from '@/types/events'

function normalizeRecording(recording: ActiveRecording): ActiveRecording {
  return {
    ...recording,
    streamer_id: Number.parseInt(recording.streamer_id.toString())
  }
}

export const useRecordingStore = defineStore('recordings', () => {
  const settings = ref<RecordingSettings | null>(null)
  const streamerSettings = ref<StreamerRecordingSettings[]>([])
  const activeRecordings = ref<ActiveRecording[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const hasActiveRecordings = computed(() => activeRecordings.value.length > 0)
  const activeRecordingsCount = computed(() => activeRecordings.value.length)
  const hasSettings = computed(() => settings.value !== null)
  const hasError = computed(() => error.value !== null)

  let realtimeBindingCount = 0
  let realtimeUnsubs: Array<() => void> = []

  function setError(value: unknown): void {
    error.value = value instanceof Error ? value.message : String(value)
  }

  function setActiveRecordings(recordings: ActiveRecording[]): void {
    activeRecordings.value = recordings.map(normalizeRecording)
  }

  function upsertActiveRecording(recording: ActiveRecording): void {
    const normalized = normalizeRecording(recording)
    const existingIndex = activeRecordings.value.findIndex((rec) => rec.id === normalized.id)
    if (existingIndex === -1) {
      activeRecordings.value.push(normalized)
    } else {
      activeRecordings.value[existingIndex] = normalized
    }
  }

  function removeActiveRecording(recordingId?: number, streamerId?: number): void {
    if (recordingId) {
      activeRecordings.value = activeRecordings.value.filter((rec) => rec.id !== recordingId)
      return
    }
    if (streamerId) {
      activeRecordings.value = activeRecordings.value.filter((rec) => rec.streamer_id !== streamerId)
    }
  }

  function applyRealtimeEvent(event: RealtimeEvent<string>): void {
    if (event.type === 'active_recordings_update' && Array.isArray(event.data)) {
      setActiveRecordings(event.data)
      return
    }

    if (event.type === 'recording_started' && event.data) {
      upsertActiveRecording({
        ...event.data,
        id: event.data.recording_id ?? event.data.id
      } as ActiveRecording)
      return
    }

    if (event.type === 'recording_stopped') {
      removeActiveRecording(event.data?.recording_id, event.data?.streamer_id)
      return
    }

    if (event.type === 'recording_status_update') {
      const inactiveStatuses = ['completed', 'failed', 'stopped', 'cancelled']
      if (inactiveStatuses.includes(event.data?.status)) {
        removeActiveRecording(event.data?.recording_id, event.data?.streamer_id)
      }
      return
    }

    if (event.type === 'recording_completed') {
      if (event.data?.recording_id) {
        removeActiveRecording(event.data.recording_id)
        window.dispatchEvent(new CustomEvent('recording_completed', {
          detail: {
            recording_id: event.data.recording_id,
            file_path: event.data.file_path,
            stream_id: event.data?.stream_id
          }
        }))
      }
      return
    }

    if (event.type === 'recording_available' && event.data?.stream_id) {
      window.dispatchEvent(new CustomEvent('recording_available', {
        detail: {
          stream_id: event.data.stream_id,
          recording_path: event.data.recording_path,
          streamer_id: event.data?.streamer_id,
          streamer_name: event.data?.streamer_name,
          title: event.data?.title
        }
      }))
    }
  }

  function bindRealtime(): () => void {
    realtimeBindingCount += 1
    if (realtimeBindingCount === 1) {
      const realtime = useRealtimeStore()
      realtimeUnsubs = [
        realtime.onEvent('active_recordings_update', applyRealtimeEvent),
        realtime.onEvent('recording_started', applyRealtimeEvent),
        realtime.onEvent('recording_stopped', applyRealtimeEvent),
        realtime.onEvent('recording_status_update', applyRealtimeEvent),
        realtime.onEvent('recording_completed', applyRealtimeEvent),
        realtime.onEvent('recording_available', applyRealtimeEvent)
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

  async function fetchSettings(): Promise<void> {
    try {
      isLoading.value = true
      error.value = null
      settings.value = await fetchRecordingSettings()
    } catch (err) {
      setError(err)
    } finally {
      isLoading.value = false
    }
  }

  async function updateSettings(newSettings: RecordingSettings): Promise<void> {
    try {
      isLoading.value = true
      error.value = null
      settings.value = await saveRecordingSettings(newSettings)
    } catch (err) {
      setError(err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchStreamerSettings(): Promise<StreamerRecordingSettings[]> {
    try {
      isLoading.value = true
      error.value = null
      streamerSettings.value = await fetchStreamerRecordingSettings()
      return streamerSettings.value
    } catch (err) {
      setError(err)
      console.error('Error fetching streamer recording settings:', err)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function updateStreamerSettings(
    streamerId: number,
    newSettings: Partial<StreamerRecordingSettings>
  ): Promise<StreamerRecordingSettings> {
    try {
      isLoading.value = true
      error.value = null
      const updatedSettings = await saveStreamerRecordingSettings(streamerId, newSettings)
      const index = streamerSettings.value.findIndex((s) => s.streamer_id === streamerId)
      if (index !== -1) {
        streamerSettings.value[index] = updatedSettings
      }
      return updatedSettings
    } catch (err) {
      setError(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchActiveRecordings(): Promise<void> {
    try {
      isLoading.value = true
      error.value = null
      setActiveRecordings(await fetchActiveRecordingsService())
    } catch (err) {
      console.error('Error fetching active recordings:', err)
      setError(err)
      activeRecordings.value = []
    } finally {
      isLoading.value = false
    }
  }

  async function stopRecording(streamerId: number): Promise<boolean> {
    try {
      isLoading.value = true
      error.value = null
      await stopStreamerRecording(streamerId)
      await fetchActiveRecordings()
      return true
    } catch (err) {
      console.error('Error stopping recording:', err)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function cleanupOldRecordings(streamerId: number): Promise<CleanupResult> {
    try {
      isLoading.value = true
      error.value = null
      return await cleanupRecordings(streamerId)
    } catch (err) {
      console.error('Error cleaning up recordings:', err)
      setError(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function getDefaultCleanupPolicy(): CleanupPolicy {
    return {
      type: CleanupPolicyType.COUNT,
      threshold: 10,
      preserve_favorites: true,
      preserve_categories: []
    }
  }

  async function updateCleanupPolicy(policy: CleanupPolicy): Promise<boolean> {
    try {
      isLoading.value = true
      error.value = null

      if (!settings.value) {
        await fetchSettings()
      }

      if (settings.value) {
        await updateSettings({ ...settings.value, cleanup_policy: policy })
        return true
      }

      return false
    } catch (err) {
      console.error('Error updating cleanup policy:', err)
      setError(err)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function updateStreamerCleanupPolicy(
    streamerId: number,
    policy: CleanupPolicy,
    useGlobal: boolean = false
  ): Promise<boolean> {
    try {
      isLoading.value = true
      error.value = null
      await saveStreamerCleanupPolicy(streamerId, policy, useGlobal)
      await fetchStreamerSettings()
      return true
    } catch (err) {
      console.error('Error updating streamer cleanup policy:', err)
      return false
    } finally {
      isLoading.value = false
    }
  }

  async function runCustomCleanup(
    streamerId: number,
    customPolicy?: CleanupPolicy
  ): Promise<CleanupResult> {
    try {
      isLoading.value = true
      error.value = null
      return await runCleanup(streamerId, customPolicy)
    } catch (err) {
      console.error('Error running custom cleanup:', err)
      setError(err)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function getStreamerStorageUsage(streamerId: number): Promise<StreamerStorageUsage> {
    try {
      isLoading.value = true
      error.value = null
      return await fetchStreamerStorageUsage(streamerId)
    } catch (err) {
      console.error('Error getting streamer storage usage:', err)
      setError(err)
      return {
        totalSize: 0,
        recordingCount: 0,
        oldestRecording: '',
        newestRecording: ''
      }
    } finally {
      isLoading.value = false
    }
  }

  async function getAvailableCategories(): Promise<CategoryOption[]> {
    try {
      return await fetchAvailableCategories()
    } catch (err) {
      console.error('Error fetching categories:', err)
      return []
    }
  }

  return {
    settings,
    streamerSettings,
    activeRecordings,
    isLoading,
    error,
    hasActiveRecordings,
    activeRecordingsCount,
    hasSettings,
    hasError,
    setActiveRecordings,
    upsertActiveRecording,
    removeActiveRecording,
    applyRealtimeEvent,
    bindRealtime,
    fetchSettings,
    updateSettings,
    fetchStreamerSettings,
    updateStreamerSettings,
    fetchActiveRecordings,
    stopRecording,
    cleanupOldRecordings,
    getDefaultCleanupPolicy,
    updateCleanupPolicy,
    updateStreamerCleanupPolicy,
    runCustomCleanup,
    getStreamerStorageUsage,
    getAvailableCategories
  }
})
