import { afterEach, describe, expect, it, vi } from 'vitest'

import { videoApi } from '@/services/api'

describe('mock video API facade', () => {
  afterEach(() => vi.unstubAllGlobals())

  const mockModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it : it.skip

  mockModeIt('matches the backend-backed player facade without browser fetches', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(videoApi.getAll()).resolves.toEqual(expect.any(Array))
    await expect(videoApi.getChapters(42)).resolves.toEqual([
      { id: 1, title: 'Stream Start', start: 0, end: 600 }
    ])
    expect(videoApi.getVideoStreamUrl(42)).toBe('/api/videos/42/stream')
    await expect(videoApi.createShareToken(42, {})).resolves.toMatchObject({
      success: true,
      share_url: '/api/videos/public/42?token=mock-share-token',
      expires_in: '24 hours'
    })
    await expect(videoApi.delete(42)).resolves.toEqual({ success: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
