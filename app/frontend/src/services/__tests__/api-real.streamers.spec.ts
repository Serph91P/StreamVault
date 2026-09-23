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

import { streamersApi } from '@/services/api-real'

describe('real streamers API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('preserves the streamers read and delete request contract', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ streamers: [] }), {
        headers: { 'content-type': 'application/json' }
      }))
      .mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(streamersApi.getAll()).resolves.toEqual({ streamers: [] })
    await expect(streamersApi.delete('streamer-1')).resolves.toBeUndefined()
    await expect(streamersApi.delete('streamer-1', true)).resolves.toBeUndefined()

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/streamers', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/streamers/streamer-1', expect.objectContaining({
      method: 'DELETE',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/streamers/streamer-1?delete_recordings=true', expect.objectContaining({
      method: 'DELETE',
      credentials: 'include'
    }))
  })
})