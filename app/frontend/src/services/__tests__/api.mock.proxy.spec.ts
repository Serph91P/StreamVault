import { afterEach, describe, expect, it, vi } from 'vitest'
import { proxyApi } from '@/services/api'

describe('mock proxy API facade', () => {
  afterEach(() => vi.unstubAllGlobals())

  const mockModeIt = import.meta.env.VITE_USE_MOCK_DATA === 'true' ? it : it.skip

  mockModeIt('matches real response envelopes and never performs browser proxy fetches', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const listed = await proxyApi.getAll()
    expect(listed).toEqual({
      proxies: expect.any(Array),
      system_config: expect.objectContaining({ proxy_health_check_interval_seconds: 300 })
    })
    expect(listed.proxies).not.toHaveLength(0)
    for (const proxy of listed.proxies) {
      expect(proxy.proxy_url).toBe(proxy.masked_url)
      expect(proxy.proxy_url).not.toMatch(/^[A-Za-z][A-Za-z\d+.-]*:\/\//)
      expect(proxy.proxy_url).not.toContain('@')
    }
    expect(listed.proxies).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 1,
        proxy_url: 'proxy1.example.com:8080',
        masked_url: 'proxy1.example.com:8080'
      }),
      expect.objectContaining({
        id: 2,
        proxy_url: 'proxy2.example.com:8080',
        masked_url: 'proxy2.example.com:8080'
      })
    ]))

    const added = await proxyApi.add({ proxy_url: 'http://user:secret@new.example:8080', priority: 8 })
    expect(added).toEqual(expect.objectContaining({ success: true, proxy_id: expect.any(Number), message: expect.any(String) }))
    const addedProxy = (await proxyApi.getAll()).proxies.find(proxy => proxy.id === added.proxy_id)
    expect(addedProxy).toEqual(expect.objectContaining({
      proxy_url: 'new.example:8080',
      masked_url: 'new.example:8080'
    }))
    expect(JSON.stringify(addedProxy)).not.toContain('secret')
    await expect(proxyApi.toggle(added.proxy_id)).resolves.toEqual(expect.objectContaining({
      success: true, enabled: false, message: expect.any(String)
    }))
    await expect(proxyApi.test(added.proxy_id)).resolves.toEqual({
      success: true,
      result: expect.objectContaining({
        proxy_id: added.proxy_id,
        health_status: 'healthy',
        response_time_ms: 123,
        consecutive_failures: 0,
        enabled: false,
        error: null
      })
    })
    await expect(proxyApi.updatePriority(added.proxy_id, 2)).resolves.toEqual(expect.objectContaining({ success: true, message: expect.any(String) }))
    await expect(proxyApi.updateConfig({ proxy_max_consecutive_failures: 5 })).resolves.toEqual({
      success: true,
      message: expect.any(String),
      config: expect.objectContaining({ proxy_max_consecutive_failures: 5 })
    })
    await expect(proxyApi.delete(added.proxy_id)).resolves.toEqual(expect.objectContaining({ success: true, message: expect.any(String) }))

    const defaultPort = await proxyApi.add({ proxy_url: 'http://user:default-secret@new.example:80' })
    const defaultPortProxy = (await proxyApi.getAll()).proxies.find(proxy => proxy.id === defaultPort.proxy_id)
    expect(defaultPortProxy).toEqual(expect.objectContaining({
      proxy_url: 'new.example:80',
      masked_url: 'new.example:80'
    }))
    expect(JSON.stringify(defaultPortProxy)).not.toContain('default-secret')
    await proxyApi.delete(defaultPort.proxy_id)

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
