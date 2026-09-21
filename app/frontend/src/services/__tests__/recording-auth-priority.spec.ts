import { afterEach, describe, expect, it, vi } from 'vitest'

import { saveStreamerRecordingSettings } from '@/services/recording'


describe('Twitch authentication priority settings', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends the bounded channel priority through the settings API', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        streamer_id: 7,
        username: 'priority-channel',
        enabled: true,
        twitch_auth_priority: 100
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    const saved = await saveStreamerRecordingSettings(7, {
      twitch_auth_priority: 100
    })

    expect(saved.twitch_auth_priority).toBe(100)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/recording/streamers/7',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          streamer_id: 7,
          twitch_auth_priority: 100
        })
      })
    )
  })
})
