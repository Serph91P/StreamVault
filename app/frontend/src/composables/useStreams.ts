import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Stream } from '@/types/streams'

export function useStreams() {
  const streams = ref<Stream[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const streamerInfo = ref(null)
  const currentStreamerId = ref<string | number | null>(null)

  /**
   * Fetch all streams for a specific streamer
   */
  const fetchStreams = async (streamerId: string | number) => {
    if (!streamerId) return
    
    currentStreamerId.value = streamerId
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch(`/api/streamers/${streamerId}/streams`, {
        credentials: 'include' // CRITICAL: Required to send session cookie
      })
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Failed to fetch streams for streamer ID ${streamerId}`)
      }
      
      const data = await response.json()
      // Safety net: only keep streams that belong to the requested streamer
      streams.value = Array.isArray(data.streams)
        ? data.streams.filter((s: Stream) => Number(s.streamer_id) === Number(streamerId))
        : []
      streamerInfo.value = data.streamer
      
    } catch (err) {
      console.error('Error fetching streams:', err)
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
      streams.value = []
    } finally {
      isLoading.value = false
    }
  }

  // Constants
  const REFRESH_DELAY_MS = 1000

  /**
   * Refresh streams when a recording is completed
   */
  const handleRecordingCompleted = (event: CustomEvent) => {
    console.log('Recording completed, refreshing streams...', event.detail)
    if (currentStreamerId.value) {
      // Delay refresh slightly to ensure database is updated
      setTimeout(() => {
        if (currentStreamerId.value) {
          fetchStreams(currentStreamerId.value)
        }
      }, REFRESH_DELAY_MS)
    }
  }

  /**
   * Refresh streams when a recording becomes available (post-processing completed)
   */
  const handleRecordingAvailable = (event: CustomEvent) => {
    console.log('Recording available, refreshing streams...', event.detail)
    if (currentStreamerId.value) {
      // Refresh immediately since this is the final state
      fetchStreams(currentStreamerId.value)
    }
  }

  // Listen for recording completion events
  onMounted(() => {
    window.addEventListener('recording_completed', handleRecordingCompleted as EventListener)
    window.addEventListener('recording_available', handleRecordingAvailable as EventListener)
  })

  onUnmounted(() => {
    window.removeEventListener('recording_completed', handleRecordingCompleted as EventListener)
    window.removeEventListener('recording_available', handleRecordingAvailable as EventListener)
  })

  return {
    streams,
    isLoading,
    error,
    streamerInfo,
    fetchStreams
  }
}
