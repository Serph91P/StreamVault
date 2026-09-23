import { afterEach, describe, expect, it, vi } from 'vitest'

const { routerPush, clearSessionToken, clearSessionStorage } = vi.hoisted(() => ({
  routerPush: vi.fn(() => Promise.resolve()),
  clearSessionToken: vi.fn(),
  clearSessionStorage: vi.fn()
}))

vi.mock('@/router', () => ({ default: { push: routerPush } }))
vi.mock('@/services/storage', () => ({
  appStorage: { clearSessionToken, clearSessionStorage }
}))

import { proxyApi } from '@/services/api-real'

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' }
  })
}

describe('real proxy API facade', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('preserves every fixed backend method, path, credential, body and query contract', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json({ success: true })))
    vi.stubGlobal('fetch', fetchMock)

    await proxyApi.getAll()
    await proxyApi.add({ proxy_url: 'https://proxy.example:443', priority: 4 })
    await proxyApi.delete(7)
    await proxyApi.toggle(7)
    await proxyApi.test(7)
    await proxyApi.updatePriority(7, 9)
    await proxyApi.updateConfig({
      enable_proxy: false,
      proxy_health_check_enabled: true,
      proxy_health_check_interval_seconds: 60,
      proxy_max_consecutive_failures: 10,
      fallback_to_direct_connection: false
    })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/proxy/list', expect.objectContaining({
      method: 'GET', credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/proxy/add', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({ proxy_url: 'https://proxy.example:443', priority: 4 })
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(3, '/api/proxy/7', expect.objectContaining({
      method: 'DELETE', credentials: 'include'
    }))
    expect(fetchMock).toHaveBeenNthCalledWith(4, '/api/proxy/7/toggle', expect.objectContaining({
      method: 'POST', credentials: 'include'
    }))
    expect(fetchMock.mock.calls[3][1]).not.toHaveProperty('body')
    expect(fetchMock).toHaveBeenNthCalledWith(5, '/api/proxy/7/test', expect.objectContaining({
      method: 'POST', credentials: 'include'
    }))
    expect(fetchMock.mock.calls[4][1]).not.toHaveProperty('body')
    expect(fetchMock).toHaveBeenNthCalledWith(6, '/api/proxy/7/update-priority', expect.objectContaining({
      method: 'POST', credentials: 'include', body: JSON.stringify({ priority: 9 })
    }))

    const [configUrl, configOptions] = fetchMock.mock.calls[6]
    const parsedConfigUrl = new URL(String(configUrl), 'http://streamvault.local')
    expect(parsedConfigUrl.pathname).toBe('/api/proxy/config/update')
    expect(Object.fromEntries(parsedConfigUrl.searchParams)).toEqual({
      enable_proxy: 'false',
      proxy_health_check_enabled: 'true',
      proxy_health_check_interval_seconds: '60',
      proxy_max_consecutive_failures: '10',
      fallback_to_direct_connection: 'false'
    })
    expect(configOptions).toEqual(expect.objectContaining({ method: 'POST', credentials: 'include' }))
    expect(configOptions).not.toHaveProperty('body')
  })

  it('surfaces FastAPI string validation detail safely', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({
      detail: 'Health check interval must be at least 60 seconds'
    }, 400)))

    await expect(proxyApi.updateConfig({ proxy_health_check_interval_seconds: 59 }))
      .rejects.toMatchObject({
        message: 'Health check interval must be at least 60 seconds',
        status: 400,
        detail: 'Health check interval must be at least 60 seconds'
      })
  })
})
