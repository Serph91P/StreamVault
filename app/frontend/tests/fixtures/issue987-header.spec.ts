import { expect, test, type WebSocketRoute } from '@playwright/test'
import { syntheticReply } from './issue828SyntheticApi'

// Real built global caller; only read-only HTTP/auth DTOs and WS peers are synthetic.
for (const reset of [true, false]) {
  for (const repair of ['failed', 'pending'] as const) {
    test(`closed combined header: reset=${reset}, recording repair=${repair}, then real status recovery`, async ({ page }, info) => {
      const peers: WebSocketRoute[] = []
      const reads: Record<string, number> = {}
      const unexpected: string[] = [], writes: string[] = [], errors: string[] = []
      let lost = false, recovered = false
      let releaseRecording: (() => void) | undefined
      const stats = { total_tasks: 0, completed_tasks: 0, failed_tasks: 0, retried_tasks: 0, pending_tasks: 0, active_tasks: 0, workers: 1, is_running: true }
      const recording = { id: 987, streamer_id: 1, stream_id: 987, streamer_name: 'last-known-recording', title: 'Synthetic', started_at: '2026-11-01T11:00:00Z', file_path: '/synthetic', status: 'recording', duration: 3600 }
      const queuePaths = ['/api/background-queue/stats', '/api/background-queue/active-tasks', '/api/background-queue/recent-tasks']
      page.on('pageerror', error => errors.push(error.message))
      await page.routeWebSocket(/.*/, socket => {
        if (socket.url() !== 'ws://127.0.0.1:4187/ws') { unexpected.push(socket.url()); return socket.close() }
        peers.push(socket)
        socket.send(JSON.stringify({ type: 'connection.status', data: { generation: lost && reset ? 'new' : 'old' } }))
      })
      await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url())
        if (url.origin !== 'http://127.0.0.1:4187') { unexpected.push(url.href); return route.abort('blockedbyclient') }
        if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
        if (request.method() !== 'GET') { writes.push(`${request.method()} ${url.pathname}`); return route.fulfill({ status: 405, json: { detail: 'Synthetic read-only fixture' } }) }
        reads[url.pathname] = (reads[url.pathname] ?? 0) + 1
        if (url.pathname === '/api/realtime/events') return route.fulfill({ json: { since: 100, events: [], reset, gap: !reset, generation: reset ? 'new' : 'old', latest_event_id: reset ? 1 : 103, oldest_event_id: reset ? 1 : 103, retained_events: 0, max_retained_events: 500 } })
        if (url.pathname === '/api/status/active-recordings') {
          if (lost && !recovered) {
            if (repair === 'failed') return route.fulfill({ status: 503, json: { detail: 'Synthetic recording status HTTP failure' } })
            await new Promise<void>(resolve => { releaseRecording = resolve })
          }
          return route.fulfill({ json: { active_recordings: [{ ...recording, streamer_name: recovered ? 'fresh-recording' : recording.streamer_name }] } })
        }
        if (url.pathname.startsWith('/api/background-queue/')) return route.fulfill({ json: url.pathname.endsWith('/stats') ? stats : [] })
        const reply = syntheticReply(url.pathname + url.search)
        if (reply.status !== 200) unexpected.push(url.pathname)
        return route.fulfill({ status: reply.status, json: reply.body })
      })
      await page.clock.install({ time: new Date('2026-11-01T12:00:00Z') })
      await page.clock.pauseAt(new Date('2026-11-01T12:00:00Z'))
      await page.goto('/videos')
      await expect.poll(() => peers.length).toBe(1)
      const trigger = page.locator('.queue-status-indicator')
      await expect(page.locator('.queue-count')).toHaveText('1')
      await expect(trigger).toHaveAttribute('aria-label', 'Open background queue, Queue 1 active job')
      await expect(trigger.locator('.progress-bar')).toHaveCount(1)
      peers[0].send(JSON.stringify({ type: 'background_queue_update', event_id: 100, data: { stats, active_tasks: [], recent_tasks: [] } }))
      await page.clock.runFor(1000)
      const before = { ...reads }
      lost = true
      peers[0].close({ code: 1012, reason: 'Synthetic reset/gap' })
      await page.clock.runFor(1500)
      await expect.poll(() => peers.length).toBe(2)
      await expect.poll(() => reads['/api/realtime/events']).toBe(1)
      for (const path of queuePaths) await expect.poll(() => reads[path] - before[path]).toBe(1)
      await page.clock.runFor(1000)
      await expect.poll(() => reads['/api/status/active-recordings'] - before['/api/status/active-recordings']).toBe(1)
      await expect(trigger).toHaveAttribute('aria-expanded', 'false')
      await expect(trigger).toHaveAttribute('aria-label', /unavailable|outdated|last-known|stale/i)
      await expect(trigger).toContainText(/outdated|last-known|stale/i)
      await expect(page.locator('.queue-count')).toHaveText('?')
      await expect(trigger.locator('.progress-bar')).toHaveCount(0)
      await page.screenshot({ path: info.outputPath('closed-header-stale.png'), fullPage: true })
      if (info.project.name === 'touch') await trigger.tap(); else await trigger.click()
      const panel = page.getByRole('dialog', { name: 'Background Queue' })
      await expect(panel).toContainText('Recording status may be outdated')
      await expect(panel).toContainText('last-known-recording')
      await expect(panel.locator('.stats-section')).toContainText('Total:0')
      await panel.getByRole('button', { name: 'Close background queue' }).click()
      await page.clock.runFor(300) // Finish the real closing transition before another native click.
      recovered = true
      if (repair === 'pending') {
        releaseRecording!()
      } else {
        // Exercise the existing shared-owner reconnect refresh, not a store assignment.
        peers[1].close({ code: 1012, reason: 'Synthetic recovery' })
        await page.clock.runFor(1500)
        await expect.poll(() => peers.length).toBe(3)
        await expect.poll(() => reads['/api/realtime/events']).toBe(2)
        await page.clock.runFor(1000)
        await expect.poll(() => reads['/api/status/active-recordings'] - before['/api/status/active-recordings']).toBe(2)
      }
      await expect(trigger).toHaveAttribute('aria-label', 'Open background queue, Queue 1 active job')
      await expect(trigger).toHaveAttribute('aria-expanded', 'false')
      await expect(page.locator('.queue-count')).toHaveText('1')
      await expect(trigger).not.toContainText(/outdated|last-known|stale/i)
      await expect(trigger.locator('.progress-bar')).toHaveCount(1)
      if (info.project.name === 'touch') await trigger.tap(); else await trigger.click()
      await expect(panel).toContainText('fresh-recording')
      await expect(panel).not.toContainText('Recording status may be outdated')
      expect(errors).toEqual([])
      expect(unexpected).toEqual([])
      expect(writes).toEqual([])
      await info.attach('requests', { body: JSON.stringify({ before, after: reads, repair, reset, errors, unexpected, writes }), contentType: 'application/json' })
    })
  }
}
