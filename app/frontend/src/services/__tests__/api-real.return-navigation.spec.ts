import { afterEach, describe, expect, it, vi } from 'vitest'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
  window.history.replaceState({}, '', '/')
})

describe('API auth-loss return navigation', () => {
  it.each([false, true])('retains the guarded deep link after parallel late 401s (visited=%s)', async (visited) => {
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    let refreshes = 0
    let held = 0
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/auth/setup') return json({ setup_required: false, welcome_completed: true })
      if (url === '/auth/check') return json({ authenticated: false })
      if (url === '/auth/refresh') {
        refreshes++
        await gate
        return json({}, 401)
      }
      if (url.startsWith('/api/')) {
        held++
        await gate
        return json({}, 401)
      }
      throw new Error(`Unexpected request: ${url}`)
    }))
    const { default: router } = await import('@/router')
    const { default: api } = await import('@/services/api-real')
    if (visited) await router.push('/auth/login')
    const pending = Promise.allSettled([
      api.get('/api/streamers'), api.get('/api/status/system'), api.get('/api/notifications/state'),
    ])
    await router.push('/streamers?probe=synthetic#recording')
    expect(router.currentRoute.value.query.returnTo).toBe('/streamers?probe=synthetic#recording')
    expect(held).toBe(3)
    release()
    const results = await pending
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/auth/login'))
    // Await the API-triggered navigation, not merely the route that was already visible.
    await new Promise(resolve => setTimeout(resolve, 0))
    expect(results.every(result => result.status === 'rejected')).toBe(true)
    expect(refreshes).toBe(1)
    expect(router.currentRoute.value.query.returnTo).toBe('/streamers?probe=synthetic#recording')
  })

  it.each([
    'https://example.invalid', '//example.invalid', 'javascript:alert(1)',
    '/auth/login?returnTo=/videos/42', '/auth/setup?returnTo=//example.invalid',
  ])('does not preserve an unsafe or nested auth return: %s', async (returnTo) => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === '/auth/setup') return json({ setup_required: false, welcome_completed: true })
      if (String(input) === '/auth/check') return json({ authenticated: false })
      return json({}, 401)
    }))
    const { default: router } = await import('@/router')
    const { default: api } = await import('@/services/api-real')
    await router.push({ path: '/auth/login', query: { returnTo } })
    await expect(api.get('/api/streamers')).rejects.toMatchObject({ code: 'auth_lost' })
    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/auth/login'))
  })

  it('retains the current protected route when auth expires after navigation', async () => {
    let authenticated = true
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === '/auth/setup') return json({ setup_required: false, welcome_completed: true })
      if (String(input) === '/auth/check') return json({ authenticated })
      return json({}, 401)
    }))
    const { default: router } = await import('@/router')
    const { default: api } = await import('@/services/api-real')
    await router.push('/videos/42?from=library#details')
    authenticated = false
    await expect(api.get('/api/streamers')).rejects.toMatchObject({ code: 'auth_lost' })
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/auth/login'))
    expect(router.currentRoute.value.query.returnTo).toBe('/videos/42?from=library#details')
  })
})
