import { ref, computed } from 'vue'
import type { Stream } from '@/types/streams'

export function useStreams() {
  const streams = ref<Stream[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const streamerInfo = ref(null)

  /**
   * Fetch all streams for a specific streamer
   */
  const fetchStreams = async (streamerId: string | number) => {
    if (!streamerId) return
    
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch(`/api/streamers/${streamerId}/streams`)
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || `Failed to fetch streams for streamer ID ${streamerId}`)
      }
      
      const data = await response.json()
      streams.value = data.streams
      streamerInfo.value = data.streamer
      
    } catch (err) {
      console.error('Error fetching streams:', err)
      error.value = err instanceof Error ? err.message : 'Unknown error occurred'
      streams.value = []
    } finally {
      isLoading.value = false
    }
  }

  return {
    streams,
    isLoading,
    error,
    streamerInfo,
    fetchStreams
  }
}
