import { test, expect, type WebSocketRoute } from '@playwright/test'
import { syntheticReply } from './issue828SyntheticApi'

// Auth, surrounding DTOs and WebSocket are synthetic; the optional harness
// forwards actual registered notification-router/SQLite responses.
const routerUrl = process.env.STREAMVAULT_NOTIFICATION_ROUTER_URL
for (const mobile of [false, true]) {
  test.describe(mobile ? 'touch pending global action' : 'desktop pending global action', () => {
    test.use({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 }, isMobile: mobile, hasTouch: mobile })
    test('new live notification after committed cutoff stays unread when the pending reply arrives', async ({ page }, testInfo) => {
      let socket: WebSocketRoute | undefined
      let committed = false
      let timestamp = ''
      let release!: () => void
      const held = new Promise<void>(resolve => { release = resolve })
      const exchanges: unknown[] = []
      const errors: string[] = []
      const writes: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.routeWebSocket(/.*/, peer => {
        socket = peer
        peer.onMessage(message => { if (String(message).includes('ping')) peer.send(JSON.stringify({ type: 'pong' })) })
      })
      await page.route('**/*', async route => {
        const request = route.request()
        const url = new URL(request.url())
        if (url.origin !== 'http://127.0.0.1:4188') return route.abort('blockedbyclient')
        if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
        if (url.pathname.startsWith('/api/notifications/')) {
          const response = routerUrl ? await route.fetch({ url: routerUrl + url.pathname }) : undefined
          if (request.method() !== 'GET') writes.push(url.pathname)
          if (url.pathname.endsWith('/mark-read')) {
            timestamp = request.postDataJSON().timestamp
            committed = true
            await held
          }
          const body = response ? await response.json() : {
            success: true, last_read_timestamp: timestamp || null, last_cleared_timestamp: null, unread_count: 0,
          }
          exchanges.push({ method: request.method(), path: url.pathname, status: response?.status() ?? 200, body })
          return response ? route.fulfill({ response }) : route.fulfill({ json: body })
        }
        const reply = syntheticReply(url.pathname + url.search, request.method())
        return route.fulfill({ status: reply.status, json: reply.body })
      })
      await page.goto('/streamers')
      const bell = page.locator('.app-header button[aria-controls="notification-panel"]')
      await expect(bell).toBeVisible()
      await expect.poll(() => Boolean(socket)).toBe(true)
      await expect.poll(() => exchanges.length).toBeGreaterThan(0)
      const send = (id: string, created_at: string) => socket!.send(JSON.stringify({ type: 'notification_event', data: {
        event_id: `989-pending-${id}`, dedupe_key: `989-pending-${id}`, title: id, body: 'Synthetic controlled pending response',
        type: 'stream.online', severity: 'info', source: 'test', created_at, target_url: '/videos',
      } }))
      send('before-click', new Date().toISOString())
      await expect(bell.locator('.badge')).toHaveText('1')
      await bell.click()
      const panel = page.locator('#notification-panel')
      await expect(panel.locator('.notification-item')).toHaveCount(1)
      const markAll = panel.getByRole('button', { name: 'Mark all notifications read', exact: true })
      if (mobile) await markAll.tap()
      else await markAll.click()
      await expect.poll(() => committed).toBe(true)
      await expect.poll(() => Date.now()).toBeGreaterThan(Date.parse(timestamp))
      const liveTime = new Date().toISOString()
      send('after-click', liveTime)
      const newItem = panel.locator('.notification-item').filter({ has: page.getByRole('heading', { name: 'after-click', exact: true }) })
      await expect(newItem).toHaveClass(/unread/)
      await page.screenshot({ path: testInfo.outputPath('before-response.png') })
      release()
      await expect(panel.getByRole('button', { name: 'Clear all notifications', exact: true })).toBeEnabled()
      await page.screenshot({ path: testInfo.outputPath('after-response.png') })
      await expect(newItem).toHaveClass(/unread/)
      await expect(bell.locator('.badge')).toHaveText('1')
      await page.reload()
      await bell.click()
      await expect(newItem).toHaveClass(/unread/)
      send('after-click', liveTime)
      await expect(panel.locator('.notification-item')).toHaveCount(2)
      await expect(newItem).toHaveClass(/unread/)
      await expect(bell.locator('.badge')).toHaveText('1')
      await panel.locator('.filter-menu-toggle').click()
      await panel.getByRole('button', { name: /^Unread/ }).click()
      await expect(panel.locator('.notification-item')).toHaveCount(1)
      await expect(newItem).toBeVisible()
      expect(writes).toEqual(['/api/notifications/mark-read'])
      expect(errors).toEqual([])
      await testInfo.attach('router-exchanges', { body: JSON.stringify({ mode: routerUrl ? 'registered router + SQLite' : 'synthetic timestamp HTTP', exchanges }), contentType: 'application/json' })
    })
  })
}
