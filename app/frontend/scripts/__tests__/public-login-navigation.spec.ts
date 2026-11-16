// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { publicLoginNavigation } from '../../vite.config'

function matches(path: string, mode = 'navigate', origin = 'https://app.test') {
  return Reflect.apply(publicLoginNavigation.urlPattern as CallableFunction, undefined, [{
    url: new URL(path, origin), sameOrigin: origin === 'https://app.test',
    request: { mode },
  }])
}

describe('public login document HTTP cache migration', () => {
  it('matches only same-origin login navigations and keeps network-only GET handling', () => {
    expect(publicLoginNavigation.handler).toBe('NetworkOnly')
    expect(publicLoginNavigation.method).toBe('GET')
    expect(matches('/auth/login')).toBe(true)
    expect(matches('/auth/login?returnTo=%2Fsettings')).toBe(true)
    for (const path of ['/auth/login/', '/auth/login/private', '/auth/setup', '/auth/check', '/api/auth/login', '/api/system/info', '/ws', '/settings']) {
      expect(matches(path), path).toBe(false)
    }
    expect(matches('/auth/login', 'cors')).toBe(false)
    expect(matches('/auth/login', 'navigate', 'https://other.test')).toBe(false)
  })

  it('uses the supported Workbox request hook to bypass old HTTP entries without storing auth HTML', async () => {
    const plugin = publicLoginNavigation.options?.plugins?.[0]
    expect(plugin?.requestWillFetch).toBeTypeOf('function')
    const original = new Request('https://app.test/auth/login?returnTo=%2Fsettings', {
      credentials: 'include', headers: { Accept: 'text/html' }, redirect: 'manual',
    })
    const request = await Reflect.apply(plugin!.requestWillFetch!, undefined, [{ request: original }]) as Request
    expect(request.cache).toBe('no-store')
    expect(request.url).toBe(original.url)
    expect(request.credentials).toBe(original.credentials)
    expect(request.headers.get('accept')).toBe('text/html')
    expect(request.redirect).toBe(original.redirect)
    expect(original.cache).toBe('default')
    expect(publicLoginNavigation.options?.cacheName).toBeUndefined()
    expect(plugin?.cacheWillUpdate).toBeUndefined()
  })
})
