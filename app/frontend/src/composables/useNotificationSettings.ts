import { ref, type Ref } from 'vue'
import type { NotificationSettings, StreamerNotificationSettings } from '@/types/settings'
import { settingsApi } from '@/services/api'

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
      settings.value = await settingsApi.getGlobalSettings()
    } catch (error) {
      console.error('Failed to fetch settings:', error)
    }
  }

  const updateSettings = async (newSettings: Partial<NotificationSettings>): Promise<void> => {
    settings.value = await settingsApi.updateGlobalSettings(newSettings)
  }

  const getStreamerSettings = async () => {
    try {
      const data = await settingsApi.getStreamerSettings()
      streamerSettings.value = data
      return data
    } catch (error) {
      console.error('Failed to fetch streamer settings:', error)
      return []
    }
  }

  const updateStreamerSettings = async (streamerId: number, settings: Partial<StreamerNotificationSettings>): Promise<StreamerNotificationSettings> => {
    return settingsApi.updateStreamerSettings(streamerId, settings)
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
