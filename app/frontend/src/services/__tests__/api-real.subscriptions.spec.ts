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

import { subscriptionsApi } from '@/services/api'

describe('real subscriptions API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  const realModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it.skip : it

  realModeIt('exports the real facade and preserves the backend list and mutation request/result contract', async () => {
    const subscriptions = [{
      id: 'sub-1',
      type: 'stream.online',
      status: 'enabled',
      created_at: '2026-09-23T12:00:00Z',
      condition: { broadcaster_user_id: '42' }
    }]
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ total: 1, subscriptions }), {
        headers: { 'content-type': 'application/json' }
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        success: true,
        message: 'Resubscribed to 1 streamer(s)',
        results: [],
        total_processed: 1
      }), { headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        success: true,
        message: 'Subscription sub-1 deleted'
      }), { headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        success: true,
        deleted_subscriptions: [],
        total_deleted: 0,
        total_failed: 0
      }), { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(subscriptionsApi.getAll()).resolves.toEqual({ total: 1, subscriptions })
    await expect(subscriptionsApi.resubscribeAll()).resolves.toEqual({
      success: true,
      message: 'Resubscribed to 1 streamer(s)',
      results: [],
      total_processed: 1
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

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/streamers/subscriptions', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/streamers/resubscribe-all', expect.objectContaining({
      method: 'POST',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/streamers/subscriptions/sub-1', expect.objectContaining({
      method: 'DELETE',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/streamers/subscriptions', expect.objectContaining({
      method: 'DELETE',
      credentials: 'include'
    }))
  })
})
