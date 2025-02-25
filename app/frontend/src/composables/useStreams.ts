import { ref } from 'vue'

export interface Stream {
  id: number
  streamer_id: number
  title: string | null
  category_name: string | null
  language: string | null
  started_at: string
  ended_at: string | null
  twitch_stream_id: string
  is_live: boolean
}

export function useStreams() {
  const streams = ref<Stream[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchStreams = async (streamerId: string) => {
    isLoading.value = true
    error.value = null
    
    try {
      const response = await fetch(`/api/streamers/${streamerId}/streams`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const data = await response.json()
      streams.value = data.streams || []
    } catch (e) {
      console.error('Error fetching streams:', e)
      error.value = e instanceof Error ? e.message : 'Unknown error'
      streams.value = []
    } finally {
      isLoading.value = false
    }
  }

  return {
    streams,
    isLoading,
    error,
    fetchStreams
  }
}