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

import apiClient, { ApiRequestError } from '@/services/api-real'
import { isApiRequestError, streamersApi } from '@/services/api'

describe('ApiClient auth refresh boundary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('refreshes cookies once and retries an eligible GET request once', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ streamers: [] }), {
        status: 200,
        headers: { 'content-type': 'application/json' }
      }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/api/streamers')).resolves.toEqual({ streamers: [] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/streamers', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/auth/refresh', {
      method: 'POST',
      credentials: 'include'
    })
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/streamers', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(clearSessionToken).not.toHaveBeenCalled()
  })

  it('shares one refresh between concurrent safe 401s and retries each request once', async () => {
    let resolveRefresh: (response: Response) => void
    const refreshResponse = new Promise<Response>(resolve => {
      resolveRefresh = resolve
    })
    const requestCounts = new Map<string, number>()
    const fetchMock = vi.fn((url: string) => {
      if (url === '/auth/refresh') {
        return refreshResponse
      }

      const count = (requestCounts.get(url) ?? 0) + 1
      requestCounts.set(url, count)
      return Promise.resolve(count === 1
        ? new Response(null, { status: 401 })
        : new Response(JSON.stringify({ url }), {
            status: 200,
            headers: { 'content-type': 'application/json' }
          }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const first = apiClient.get('/api/streamers')
    const second = apiClient.get('/api/status/system')

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    expect(fetchMock).toHaveBeenCalledWith('/auth/refresh', {
      method: 'POST',
      credentials: 'include'
    })

    resolveRefresh!(new Response(null, { status: 204 }))

    await expect(Promise.all([first, second])).resolves.toEqual([
      { url: '/api/streamers' },
      { url: '/api/status/system' }
    ])
    expect(fetchMock).toHaveBeenCalledTimes(5)
    expect(clearSessionToken).not.toHaveBeenCalled()
  })

  it('shares failed refresh auth loss and cleanup between concurrent safe 401s', async () => {
    let resolveRefresh: (response: Response) => void
    const refreshResponse = new Promise<Response>(resolve => {
      resolveRefresh = resolve
    })
    const fetchMock = vi.fn((url: string) => {
      if (url === '/auth/refresh') {
        return refreshResponse
      }
      return Promise.resolve(new Response(null, { status: 401 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    const first = apiClient.get('/api/streamers')
    const second = apiClient.get('/api/status/system')

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    resolveRefresh!(new Response(null, { status: 401 }))

    await expect(Promise.allSettled([first, second])).resolves.toEqual([
      expect.objectContaining({
        status: 'rejected',
        reason: expect.objectContaining({ name: 'ApiRequestError', code: 'auth_lost', status: 401 })
      }),
      expect.objectContaining({
        status: 'rejected',
        reason: expect.objectContaining({ name: 'ApiRequestError', code: 'auth_lost', status: 401 })
      })
    ])
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('rejects a failed refresh as one normalized auth-loss error', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/api/streamers')).rejects.toMatchObject({
      name: 'ApiRequestError',
      code: 'auth_lost',
      status: 401
    } satisfies Partial<ApiRequestError>)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('treats a refresh network failure as one normalized auth loss', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockRejectedValueOnce(new TypeError('network unavailable'))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/api/streamers')).rejects.toMatchObject({
      name: 'ApiRequestError',
      code: 'auth_lost',
      status: 401
    } satisfies Partial<ApiRequestError>)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('rejects a repeated 401 after refresh without another refresh attempt', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/api/streamers')).rejects.toMatchObject({
      name: 'ApiRequestError',
      code: 'auth_lost',
      status: 401
    } satisfies Partial<ApiRequestError>)

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('exposes the normalized auth-loss error through the public API facade', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    try {
      await streamersApi.getAll()
      throw new Error('Expected the facade to reject')
    } catch (error) {
      expect(isApiRequestError(error)).toBe(true)
      if (isApiRequestError(error)) {
        expect(error).toMatchObject({ code: 'auth_lost', status: 401 })
      }
    }
  })

  it.each([
    ['POST', () => apiClient.post('/api/recording/start/7', { force: true })],
    ['PUT', () => apiClient.put('/api/settings', { theme: 'dark' })],
    ['DELETE', () => apiClient.delete('/api/streams/7')],
    ['refresh endpoint', () => apiClient.post('/auth/refresh')]
  ])('does not replay %s requests after a 401', async (_label, request) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(request()).rejects.toMatchObject({
      name: 'ApiRequestError',
      code: 'auth_lost',
      status: 401
    } satisfies Partial<ApiRequestError>)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('does not refresh or retry an auth refresh endpoint with query parameters', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/auth/refresh', { trace: 'review' })).rejects.toMatchObject({
      name: 'ApiRequestError',
      code: 'auth_lost',
      status: 401
    } satisfies Partial<ApiRequestError>)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith('/auth/refresh?trace=review', expect.objectContaining({
      method: 'GET',
      credentials: 'include'
    }))
    expect(clearSessionToken).toHaveBeenCalledTimes(1)
    expect(clearSessionStorage).toHaveBeenCalledTimes(1)
    expect(routerPush).toHaveBeenCalledTimes(1)
  })

  it('does not add a legacy-session credential while retrying a stored media request', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiClient.get('/api/videos/7/stream')).rejects.toMatchObject({ code: 'auth_lost' })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/videos/7/stream', expect.not.objectContaining({
      headers: expect.objectContaining({ Authorization: expect.any(String) })
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/videos/7/stream', expect.not.objectContaining({
      headers: expect.objectContaining({ Authorization: expect.any(String) })
    }))
  })
})
