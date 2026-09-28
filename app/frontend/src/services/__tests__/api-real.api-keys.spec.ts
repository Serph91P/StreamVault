import { afterEach, describe, expect, it, vi } from 'vitest'

const { routerPush, clearSessionToken, clearSessionStorage } = vi.hoisted(() => ({
  routerPush: vi.fn(() => Promise.resolve()),
  clearSessionToken: vi.fn(),
  clearSessionStorage: vi.fn()
}))

vi.mock('@/router', () => ({ default: { push: routerPush } }))
vi.mock('@/services/storage', () => ({ appStorage: { clearSessionToken, clearSessionStorage } }))

import { apiKeysApi } from '@/services/api'

describe('real API-key facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  const realModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it.skip : it

  realModeIt('uses the shared client and never replays create or revoke mutations', async () => {
    const created = { id: 2, name: 'monitoring', prefix: 'sv_', key: 'secret', created_at: '2026-09-24T00:00:00Z', last_used_at: null }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(created), { headers: { 'content-type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiKeysApi.getAll()).resolves.toEqual([])
    await expect(apiKeysApi.create('monitoring')).resolves.toEqual(created)
    await expect(apiKeysApi.revoke(2)).resolves.toBeInstanceOf(Response)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/api-keys', expect.objectContaining({ method: 'GET', credentials: 'include' }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/api-keys', expect.objectContaining({ method: 'POST', body: JSON.stringify({ name: 'monitoring' }) }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/api-keys/2', expect.objectContaining({ method: 'DELETE' }))
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
