import { ref, type Ref } from 'vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

interface NotificationSettingsComposable {
  settings: Ref<NotificationSettings | null>
  streamerSettings: Ref<StreamerNotificationSettings[]>
  fetchSettings: () => Promise<void>
  updateSettings: (newSettings: Partial<NotificationSettings>) => Promise<void>
  getStreamerSettings: () => Promise<StreamerNotificationSettings[]>
  updateStreamerSettings: (streamerId: number, settings: Partial<StreamerNotificationSettings>) => Promise<StreamerNotificationSettings>
}

export function useNotificationSettings(): NotificationSettingsComposable {
  const settings: Ref<NotificationSettings | null> = ref(null)
  const streamerSettings: Ref<StreamerNotificationSettings[]> = ref([])

  const fetchSettings = async (): Promise<void> => {
    try {
      const response = await fetch('/api/settings')
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      settings.value = await response.json()
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    }
  }

  const updateSettings = async (newSettings: Partial<NotificationSettings>): Promise<void> => {
    const response = await fetch('/api/settings/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSettings)
    })
    
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to update settings')
    }
    
    settings.value = await response.json()
  }

  const getStreamerSettings = async () => {
    try {
      const response = await fetch('/api/settings/streamer')
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      const data = await response.json()
      streamerSettings.value = data
      return data
    } catch (error) {
      console.error('Failed to fetch streamer settings:', error)
      return []
    }
  }

  const updateStreamerSettings = async (
    streamerId: number, 
    settings: Partial<StreamerNotificationSettings>
  ): Promise<StreamerNotificationSettings> => {
    const response = await fetch(`/api/settings/streamer/${streamerId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    })
    return await response.json()
  }

  return {
    settings,
    streamerSettings,
    fetchSettings,
    updateSettings,
    getStreamerSettings,
    updateStreamerSettings
  }
}