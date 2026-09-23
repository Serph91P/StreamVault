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

    await expect(subscriptionsApi.getAll()).resolves.toEqual({ total: 0, subscriptions: [] })
    await expect(subscriptionsApi.resubscribeAll()).resolves.toEqual({
      success: true,
      message: 'All subscriptions resubscribed',
      results: [],
      total_processed: 0
    })
    await expect(subscriptionsApi.delete('sub-1')).resolves.toEqual({
      success: true,
      message: 'Subscription sub-1 deleted'
    })
    await expect(subscriptionsApi.deleteAll()).resolves.toEqual({
      success: true,
      deleted_subscriptions: [],
      total_deleted: 0,
      total_failed: 0
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
