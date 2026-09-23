import { afterEach, describe, expect, it, vi } from 'vitest'

import { subscriptionsApi } from '@/services/api'

describe('mock subscriptions API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const mockModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it : it.skip

  mockModeIt('matches the live subscriptions contract without browser fetches', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(subscriptionsApi.getAll()).resolves.toEqual({ subscriptions: [] })
    await expect(subscriptionsApi.resubscribeAll()).resolves.toMatchObject({
      success: true,
      message: expect.any(String)
    })
    await expect(subscriptionsApi.delete('sub-1')).resolves.toEqual({ success: true, subscriptionId: 'sub-1' })
    await expect(subscriptionsApi.deleteAll()).resolves.toEqual({ success: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
