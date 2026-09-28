import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useNotificationSettings } from '../useNotificationSettings'
import { settingsApi } from '@/services/api'

vi.mock('@/services/api', () => ({
  settingsApi: {
    getGlobalSettings: vi.fn(),
    updateGlobalSettings: vi.fn(),
    getStreamerSettings: vi.fn(),
    updateStreamerSettings: vi.fn()
  }
}))

const globalSettings = {
  notification_url: '',
  notifications_enabled: true,
  apprise_docs_url: '',
  notify_online_global: true,
  notify_offline_global: true,
  notify_update_global: true,
  notify_favorite_category_global: false
}

const streamerSettings = [{
  streamer_id: 7,
  notify_online: true,
  notify_offline: true,
  notify_update: true
}]

describe('useNotificationSettings', () => {
  beforeEach(() => vi.clearAllMocks())

  it('uses the shared settings API for reads and keeps reactive state in sync', async () => {
    vi.mocked(settingsApi.getGlobalSettings).mockResolvedValue(globalSettings)
    vi.mocked(settingsApi.getStreamerSettings).mockResolvedValue(streamerSettings)
    const notifications = useNotificationSettings()

    await notifications.fetchSettings()
    const result = await notifications.getStreamerSettings()

    expect(settingsApi.getGlobalSettings).toHaveBeenCalledOnce()
    expect(settingsApi.getStreamerSettings).toHaveBeenCalledOnce()
    expect(notifications.settings.value).toEqual(globalSettings)
    expect(notifications.streamerSettings.value).toEqual(streamerSettings)
    expect(result).toEqual(streamerSettings)
  })

  it('routes mutations through the shared API without replaying them', async () => {
    vi.mocked(settingsApi.updateGlobalSettings).mockResolvedValue(globalSettings)
    vi.mocked(settingsApi.updateStreamerSettings).mockResolvedValue(streamerSettings[0])
    const notifications = useNotificationSettings()

    await notifications.updateSettings({ notifications_enabled: true })
    await notifications.updateStreamerSettings(7, { notify_online: true })

    expect(settingsApi.updateGlobalSettings).toHaveBeenCalledOnce()
    expect(settingsApi.updateStreamerSettings).toHaveBeenCalledOnce()
    expect(notifications.settings.value).toEqual(globalSettings)
  })
})
