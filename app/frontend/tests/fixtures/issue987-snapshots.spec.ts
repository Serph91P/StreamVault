import { expect, test, type WebSocketRoute } from '@playwright/test'
import { syntheticReply } from './issue828SyntheticApi'

for (const view of ['/activity', '/streamers', '/streamers/1', '/streamers/manage']) {
for (const reset of [true, false]) {
  test(`${view}: available stale queue -> ${reset ? 'generation reset' : 'same-generation gap'} -> HTTP error -> native retry -> current snapshot`, async ({ page }, info) => {
    const peers: WebSocketRoute[] = [], unexpected: string[] = [], writes: string[] = [], errors: string[] = []
    const reads: Record<string, number> = {}
    const replayQueries: string[] = []
    let phase: 'old' | 'failed' | 'fresh' = 'old'
    let releaseReplay!: () => void
    const replayReady = new Promise<void>(resolve => { releaseReplay = resolve })
    const stats = { total_tasks: 1, completed_tasks: 0, failed_tasks: 0, retried_tasks: 0, pending_tasks: 0, active_tasks: 1, workers: 1, is_running: true }
    const task = (name: string) => ({ id: name, task_type: 'remux', status: 'running', progress: 25,
      created_at: '2026-01-01T00:00:00Z', started_at: '2026-01-01T00:00:00Z', retry_count: 0,
      payload: { streamer_name: name, stream_id: 987, recording_id: 987 } })
    const eventId = reset ? 1 : 103
    const retained = { type: 'test', event_id: eventId, data: { test_id: 'unrelated-retained-topic' } }
    page.on('pageerror', error => errors.push(error.message))
    await page.routeWebSocket(/.*/, socket => {
      if (socket.url() !== 'ws://127.0.0.1:4187/ws') { unexpected.push(socket.url()); return socket.close() }
      peers.push(socket)
      socket.send(JSON.stringify({ type: 'connection.status', data: { generation: peers.length > 1 && reset ? 'new' : 'old' } }))
    })
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin !== 'http://127.0.0.1:4187') { unexpected.push(url.href); return route.abort('blockedbyclient') }
      if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
      if (request.method() !== 'GET') {
        writes.push(`${request.method()} ${url.pathname}`)
        if (request.method() === 'POST' && url.pathname === '/auth/keepalive') return route.fulfill({ json: { authenticated: true } })
        return route.fulfill({ status: 405, json: { detail: 'Read-only synthetic fixture' } })
      }
      reads[url.pathname] = (reads[url.pathname] ?? 0) + 1
      if (url.pathname === '/api/realtime/events') {
        replayQueries.push(url.search)
        await replayReady
        return route.fulfill({ json: { since: 100, events: [retained], reset, gap: !reset,
          generation: reset ? 'new' : 'old', latest_event_id: eventId, oldest_event_id: eventId,
          retained_events: 1, max_retained_events: 500 } })
      }
      if (url.pathname.startsWith('/api/background-queue/')) {
        if (phase === 'failed' && url.pathname.endsWith('/stats')) return route.fulfill({ status: 503, json: { detail: 'Synthetic queue HTTP failure' } })
        const body = url.pathname.endsWith('/stats') ? stats : url.pathname.endsWith('/active-tasks') ? [task(phase === 'old' ? 'stale-task' : 'fresh-task')] : []
        return route.fulfill({ json: body })
      }
      const settings: Record<string, unknown> = {
        '/api/settings': { notification_url: '', notifications_enabled: false },
        '/api/settings/streamer': [], '/api/recording/streamers': [], '/api/recording/active': [],
        '/api/recording/settings': { enabled: true, output_directory: '/synthetic', default_quality: 'best', use_chapters: true, supported_codecs: ['h264'] },
        '/api/recording/filename-presets': { presets: [] }, '/api/favorites': [], '/api/categories': [], '/api/categories/': [],
        '/api/twitch/connection-status': { connected: false, valid: false, expires_at: null },
        '/api/proxy/list': { proxies: [], system_config: { enable_proxy: false, proxy_health_check_enabled: false, proxy_health_check_interval_seconds: 300, proxy_max_consecutive_failures: 3, fallback_to_direct_connection: true } },
      }
      if (url.pathname in settings) return route.fulfill({ json: settings[url.pathname] })
      const reply = syntheticReply(url.pathname + url.search)
      if (reply.status !== 200) unexpected.push(url.pathname)
      return route.fulfill({ status: reply.status, json: reply.body })
    })
    await page.clock.install({ time: new Date('2026-11-01T12:00:00Z') })
    await page.clock.pauseAt(new Date('2026-11-01T12:00:00Z'))
    await page.goto(view)
    await expect.poll(() => peers.length).toBe(1)
    await page.clock.runFor(1000)
    if (view !== '/activity') {
      const open = page.getByRole('button', { name: /Open background queue/ })
      if (info.project.name === 'touch') await open.tap()
      else await open.click()
    }
    const queue = page.getByRole(view === '/activity' ? 'region' : 'dialog', { name: 'Background Queue' })
    await expect(queue).toContainText('stale-task')
    peers[0].send(JSON.stringify({ type: 'background_queue_update', event_id: 100, data: { stats, active_tasks: [task('stale-task')], recent_tasks: [] } }))
    await expect(page.locator('.queue-count')).toHaveText('1')
    await page.screenshot({ path: info.outputPath('01-stale-before-loss.png'), fullPage: true })
    const before = { ...reads }
    phase = 'failed'
    peers[0].close({ code: 1012, reason: 'Synthetic server restart/reconnect' })
    await page.clock.runFor(1500)
    await expect.poll(() => peers.length).toBe(2)
    await expect.poll(() => replayQueries.length).toBe(1)
    peers[1].send(JSON.stringify(retained)) // Same ID in HTTP replay and buffered live delivery.
    releaseReplay()
    await expect(queue.getByRole('alert')).toContainText('Background queue updates are unavailable.')
    await expect(page.locator('.queue-count')).toHaveText('?')
    await expect(queue.locator('.task-item')).toHaveCount(0)
    const projection = page.locator(view === '/activity' ? '.home-view' : view === '/streamers' ? '.streamers-view' : view === '/streamers/manage' ? '.channel-settings-panel' : '.streamer-detail-view')
    await expect(projection).toContainText('Last-known status')
    await expect(projection).toContainText('Notification history may be incomplete')
    const failed = { ...reads }
    for (const path of ['/api/background-queue/stats', '/api/background-queue/active-tasks', '/api/background-queue/recent-tasks']) {
      expect(failed[path] - before[path]).toBe(1) // Two mounted monitors share one current read.
    }
    expect(replayQueries).toEqual(['?since=100&generation=old'])
    await page.screenshot({ path: info.outputPath('02-connected-but-unavailable.png'), fullPage: true })
    phase = 'fresh'
    const retry = queue.getByRole('button', { name: 'Retry', exact: true })
    expect((await retry.boundingBox())!.width).toBeGreaterThanOrEqual(44)
    expect(await retry.evaluate(button => {
      const range = document.createRange()
      range.selectNodeContents(button)
      return range.getClientRects().length
    })).toBe(1)
    if (info.project.name === 'touch') await retry.tap()
    else await retry.click()
    await expect(queue).toContainText('fresh-task')
    await expect(queue).not.toContainText('stale-task')
    await expect(queue.getByRole('alert')).toHaveCount(0)
    // The combined header also needs the existing delayed shared-status refresh.
    await page.clock.runFor(1000)
    await expect(page.locator('.queue-count')).toHaveText('1')
    for (const path of ['/api/background-queue/stats', '/api/background-queue/active-tasks', '/api/background-queue/recent-tasks']) {
      expect(reads[path] - failed[path]).toBe(1)
    }
    // A duplicate retained event must not trigger another repair or mutate history.
    peers[1].send(JSON.stringify(retained))
    await page.clock.runFor(1000)
    expect(reads['/api/background-queue/stats'] - failed['/api/background-queue/stats']).toBe(1)
    for (const path of ['/api/status/system', '/api/status/active-recordings', '/api/status/streamers', '/api/status/streams', '/api/status/notifications']) {
      await expect.poll(() => reads[path] - before[path]).toBe(1)
    }
    expect(errors).toEqual([])
    expect(unexpected).toEqual([])
    expect(writes.filter(write => write !== 'POST /auth/keepalive')).toEqual([])
    await page.screenshot({ path: info.outputPath('03-restored.png'), fullPage: true })
    await info.attach('synthetic-request-counts', { body: JSON.stringify({ view, reset, platform: info.project.name, before, failed, final: reads, replayQueries, writes, unexpected, errors }), contentType: 'application/json' })
  })
}
}
