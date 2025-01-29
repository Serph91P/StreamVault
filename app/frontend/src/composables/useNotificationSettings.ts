import { ref } from 'vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'

export function useNotificationSettings() {
  const settings = ref<NotificationSettings | null>(null)

  const fetchSettings = async (): Promise<void> => {
    const response = await fetch('/api/settings')
    settings.value = await response.json()
  }

  const updateSettings = async (newSettings: NotificationSettings): Promise<void> => {
    const response = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newSettings)
    })
    settings.value = await response.json()
  }

  const getStreamerSettings = async (): Promise<StreamerNotificationSettings[]> => {
    const response = await fetch('/api/settings/streamer')
    return await response.json()
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
    fetchSettings,
    updateSettings,
    getStreamerSettings,
    updateStreamerSettings
  }
}