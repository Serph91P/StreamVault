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
    const index = streamers.value.findIndex(s => s.twitch_id === twitch_id)
    if (index !== -1) {
      streamers.value[index] = {
        ...streamers.value[index],
        ...updates,
        last_updated: new Date().toISOString()
      }
      // Force reactivity update
      streamers.value = [...streamers.value]
    }
  }

  const fetchStreamers = async () => {
    isLoading.value = true
    try {
      const response = await fetch('/api/streamers')
      if (!response.ok) throw new Error('Failed to fetch streamers')
      const data = await response.json()
      streamers.value = data
    } catch (error) {
      console.error('Error fetching streamers:', error)
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
