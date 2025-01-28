import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export interface Streamer {
  id: string
  twitch_id: string
  username: string
  is_live: boolean
  title?: string
  category_name?: string
  language?: string
  last_updated?: string
}

export function useStreamers() {
  const streamers: Ref<Streamer[]> = ref([])
  const isLoading = ref(false)

  const updateStreamer = (twitch_id: string, updates: Partial<Streamer>) => {
    streamers.value = streamers.value.map(streamer => 
      streamer.twitch_id === twitch_id 
        ? { ...streamer, ...updates, last_updated: new Date().toISOString() }
        : streamer
    )
  }

  const fetchStreamers = async () => {
    isLoading.value = true
    try {
      const response = await fetch('/api/streamers')
      const data = await response.json()
      streamers.value = data
    } finally {
      isLoading.value = false
    }
  }

  const deleteStreamer = async (streamerId: string) => {
    const response = await fetch(`/api/streamers/${streamerId}`, {
      method: 'DELETE'
    })
    if (response.ok) {
      streamers.value = streamers.value.filter(s => s.id !== streamerId)
      return true
    }
    return false
  }

  return {
    streamers,
    isLoading,
    updateStreamer,
    fetchStreamers,
    deleteStreamer
  }
}
