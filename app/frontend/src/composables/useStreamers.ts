import { ref, computed } from 'vue'
import type { Ref } from 'vue'

export interface Streamer {
  id: string
  twitch_id: string
  username: string
  is_live: boolean
  is_recording: boolean  // Whether currently recording
  recording_enabled: boolean  // Whether recording is enabled for this streamer
  title?: string
  category_name?: string
  language?: string
  last_updated?: string
  profile_image_url?: string
}
export interface StreamerUpdateData {
  is_live?: boolean
  title?: string
  category_name?: string
  language?: string
  last_updated: string
}

export function useStreamers() {
  const streamers: Ref<Streamer[]> = ref([])
  const isLoading = ref(false)

  const updateStreamer = async (streamerId: string, updateData: StreamerUpdateData) => {
    console.log('useStreamers: Updating streamer:', { streamerId, updateData })
    const index = streamers.value.findIndex(s => s.id === streamerId)
    if (index !== -1) {
      console.log('useStreamers: Found streamer at index:', index)
      streamers.value[index] = {
        ...streamers.value[index],
        ...updateData
      }
      console.log('useStreamers: Updated streamer:', streamers.value[index])
    } else {
      console.warn('useStreamers: Streamer not found:', streamerId)
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
