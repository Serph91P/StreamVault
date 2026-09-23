import { afterEach, describe, expect, it, vi } from 'vitest'

import { streamersApi } from '@/services/api'

describe('mock streamers API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const mockModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it : it.skip

  mockModeIt('serves reads and deletes without browser fetches', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(streamersApi.getAll()).resolves.toMatchObject({ streamers: expect.any(Array) })
    await expect(streamersApi.delete('streamer-1')).resolves.toBeUndefined()

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
