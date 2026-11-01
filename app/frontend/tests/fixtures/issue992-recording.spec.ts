import { expect, test, type WebSocketRoute } from '@playwright/test'
import { syntheticReply } from './issue828SyntheticApi'

for (const separator of ['_', '.']) {
  test(`recording ${separator} wire forms update existing settings and status once`, async ({ page }, testInfo) => {
    const unexpected: string[] = [], writes: string[] = [], errors: string[] = []
    let peer: WebSocketRoute | undefined
    page.on('pageerror', error => errors.push(error.message))
    await page.routeWebSocket(/.*/, socket => {
      if (socket.url() !== 'ws://127.0.0.1:4192/ws') {
        unexpected.push(socket.url())
        return socket.close()
      }
      peer = socket
      socket.onMessage(message => {
        if (String(message).includes('ping')) socket.send(JSON.stringify({ type: 'pong' }))
      })
    })
    const settings: Record<string, unknown> = {
      '/api/settings': { notification_url: '', notifications_enabled: false },
      '/api/settings/streamer': [], '/api/recording/streamers': [], '/api/recording/active': [],
      '/api/recording/settings': { enabled: true, output_directory: '/synthetic', default_quality: 'best', use_chapters: true, supported_codecs: ['h264'] },
      '/api/recording/filename-presets': { presets: [] }, '/api/favorites': [], '/api/categories': [], '/api/categories/': [],
      '/api/twitch/connection-status': { connected: false, valid: false, expires_at: null },
      '/api/proxy/list': { proxies: [], system_config: { enable_proxy: false, proxy_health_check_enabled: false, proxy_health_check_interval_seconds: 300, proxy_max_consecutive_failures: 3, fallback_to_direct_connection: true } },
    }
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin !== 'http://127.0.0.1:4192') {
        unexpected.push(url.href)
        return route.abort('blockedbyclient')
      }
      if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
      if (request.method() !== 'GET') {
        writes.push(`${request.method()} ${url.pathname}`)
        if (request.method() === 'POST' && url.pathname === '/auth/keepalive') return route.fulfill({ json: { authenticated: true } })
        return route.fulfill({ status: 405, json: { detail: 'Read-only synthetic fixture' } })
      }
      if (url.pathname in settings) return route.fulfill({ json: settings[url.pathname] })
      const reply = syntheticReply(url.pathname + url.search)
      if (reply.status !== 200) unexpected.push(url.pathname)
      return route.fulfill({ status: reply.status, json: reply.body })
    })
    // Observe public DOM events only, never inject stores or invoke production internals.
    await page.addInitScript(() => {
      const effects: Array<{ type: string; detail: unknown }> = []
      Object.defineProperty(window, '__recordingEffects', { value: effects })
      for (const type of ['recording_completed', 'recording_available']) window.addEventListener(type, event => effects.push({ type, detail: (event as CustomEvent).detail }))
    })
    await page.clock.install({ time: new Date('2026-11-01T12:00:00Z') })
    await page.clock.pauseAt(new Date('2026-11-01T12:00:00Z'))
    await page.goto('/settings?section=recording')
    await expect(page.getByRole('heading', { name: 'Basic Recording Settings', exact: true })).toBeVisible()
    await expect.poll(() => Boolean(peer)).toBe(true)
    // Allow initial connection refresh to finish before supplying synthetic recording events.
    await page.clock.runFor(1000)
    await expect(page.locator('.queue-count')).toHaveText('0')
    const payload = { recording_id: 992, streamer_id: 1, stream_id: 992, streamer_name: 'Synthetic Alias Recorder', title: 'Synthetic alias recording', started_at: '2026-11-01T12:00:00Z', duration: 0, status: 'recording', file_path: '/synthetic/992.mp4' }
    let id = 0
    const send = (suffix: string, data = payload) => {
      const event = { type: `recording${separator}${suffix}`, event_id: ++id, data }
      peer!.send(JSON.stringify(event))
      return event
    }
    const cards = page.locator('.active-recordings .recording-card')
    send('started')
    await expect(cards).toHaveCount(1)
    await expect(cards).toContainText('Synthetic Alias Recorder')
    await expect(page.locator('.queue-count')).toHaveText('1')
    // Same logical callback must not duplicate the settings/store effect with multiple consumers.
    send('started')
    await expect(cards).toHaveCount(1)
    send('stopped')
    await expect(cards).toHaveCount(0)
    await expect(page.locator('.queue-count')).toHaveText('0')
    send('started')
    await expect(cards).toHaveCount(1)
    const completed = send('completed')
    await expect(cards).toHaveCount(0)
    await expect(page.locator('.queue-count')).toHaveText('0')
    peer!.send(JSON.stringify(completed)) // Existing manager event-ID replay overlap boundary.
    send('available', { ...payload, recording_path: '/synthetic/992.mp4' } as typeof payload)
    const effects = () => page.evaluate(() => (window as unknown as { __recordingEffects: Array<{ type: string; detail: unknown }> }).__recordingEffects)
    await expect.poll(effects).toEqual([
      { type: 'recording_completed', detail: { recording_id: 992, stream_id: 992, file_path: '/synthetic/992.mp4' } },
      { type: 'recording_available', detail: { stream_id: 992, recording_path: '/synthetic/992.mp4', streamer_id: 1, streamer_name: 'Synthetic Alias Recorder', title: 'Synthetic alias recording' } },
    ])
    // A new ID is a new event, not a universal exactly-once business identity.
    send('completed')
    await expect.poll(async () => (await effects()).length).toBe(3)
    expect(errors).toEqual([])
    expect(unexpected).toEqual([])
    expect(writes.filter(write => write !== 'POST /auth/keepalive')).toEqual([])
    await testInfo.attach('recording-dom-effects', { body: JSON.stringify({ separator, effects: await effects(), syntheticWrites: writes }), contentType: 'application/json' })
    await page.screenshot({ path: testInfo.outputPath('recording-completed.png') })
  })
}
