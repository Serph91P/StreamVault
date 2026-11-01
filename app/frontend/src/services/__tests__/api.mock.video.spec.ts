import { afterEach, describe, expect, it, vi } from 'vitest'

import { videoApi } from '@/services/api'
import { mockVideos } from '@/mocks/mockData'

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
    const fixture = structuredClone(mockVideos)
    const catalog: typeof mockVideos = await videoApi.getAll()
    catalog.pop()
    expect(await videoApi.getAll()).toEqual(fixture)
    expect(mockVideos).toEqual(fixture)

    const ids = [catalog[0].id, catalog[1].id]
    await expect(videoApi.deleteMultiple(ids)).resolves.toEqual(ids.map(id => ({
      id, status: 'fulfilled', value: { success: true }
    })))
    const remaining = fixture.filter(video => !ids.includes(video.id))
    expect(await videoApi.getAll()).toEqual(remaining)
    expect(mockVideos).toEqual(fixture)
    expect(catalog.map(video => video.id)).toEqual(fixture.slice(0, -1).map(video => video.id))
    await expect(videoApi.deleteMultiple([])).resolves.toEqual([])
    expect(await videoApi.getAll()).toEqual(remaining)
    expect(mockVideos).toEqual(fixture)

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
