import { afterEach, describe, expect, it, vi } from 'vitest'

const { routerPush, clearSessionToken, clearSessionStorage } = vi.hoisted(() => ({
  routerPush: vi.fn(() => Promise.resolve()),
  clearSessionToken: vi.fn(),
  clearSessionStorage: vi.fn()
}))

vi.mock('@/router', () => ({
  default: { push: routerPush }
}))

vi.mock('@/services/storage', () => ({
  appStorage: { clearSessionToken, clearSessionStorage }
}))

import { videoApi } from '@/services/api-real'

describe('real video API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('preserves catalog, chapter, share and delete request contracts', async () => {
    const catalog = [{ id: 42, title: 'Backend title' }]
    const chapters = [{ id: 1, title: 'Start', start: 0, end: 600 }]
    const share = { success: true, share_url: 'https://example.test/shared', expires_in: '24 hours' }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalog), {
        headers: { 'content-type': 'application/json' }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(chapters), {
        headers: { 'content-type': 'application/json' }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(share), {
        headers: { 'content-type': 'application/json' }
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(videoApi.getAll()).resolves.toEqual(catalog)
    await expect(videoApi.getChapters(42)).resolves.toEqual(chapters)
    expect(videoApi.getVideoStreamUrl(42)).toBe('/api/videos/42/stream')
    await expect(videoApi.createShareToken(42, {})).resolves.toEqual(share)
    await expect(videoApi.delete(42)).resolves.toBeInstanceOf(Response)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/videos', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/videos/42/chapters', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/videos/42/share-token', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: '{}'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/streams/42', expect.objectContaining({
      method: 'DELETE',
      credentials: 'include'
    }))
  })
})
