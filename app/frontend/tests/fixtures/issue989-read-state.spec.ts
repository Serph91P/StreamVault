import { expect, test, type WebSocketRoute } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { syntheticReply } from './issue828SyntheticApi'

// Optional real registered Router/SQLite harness; otherwise the documented
// timestamp-only HTTP protocol is synthetic. Auth/providers/WebSocket are synthetic in both modes.
const routerUrl = process.env.STREAMVAULT_NOTIFICATION_ROUTER_URL
for (const mobile of [false, true]) {
  test.describe(mobile ? 'local notification state touch' : 'local notification state desktop', () => {
    test.use({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 }, isMobile: mobile, hasTouch: mobile })
    test('single actions, reload/sync/replay, global intents and failures preserve truthful state', async ({ page }, testInfo) => {
      let peer: WebSocketRoute | undefined
      let state = { last_read_timestamp: null as string | null, last_cleared_timestamp: null as string | null, unread_count: 0 }
      let failure: 'state' | 'mark-read' | 'clear' | undefined
      const writes: string[] = []
      const errors: string[] = []
      const unexpected: string[] = []
      const exchanges: unknown[] = []
      page.on('pageerror', error => errors.push(error.message))
      await page.routeWebSocket(/.*/, socket => {
        peer = socket
        socket.onMessage(message => { if (String(message).includes('ping')) socket.send(JSON.stringify({ type: 'pong' })) })
      })
      await page.route('**/*', async route => {
        const request = route.request()
        const url = new URL(request.url())
        if (url.origin !== 'http://127.0.0.1:4188') {
          unexpected.push(url.origin + url.pathname)
          return route.abort('blockedbyclient')
        }
        if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
        if (url.pathname.startsWith('/api/notifications/')) {
          const action = url.pathname.split('/').at(-1)
          if (request.method() !== 'GET') writes.push(`${request.method()} ${url.pathname}`)
          if (action === failure) return route.fulfill({ status: 503, json: { detail: 'Deliberately isolated failure' } })
          if (routerUrl) {
            const response = await route.fetch({ url: routerUrl + url.pathname })
            const body = await response.json()
            exchanges.push({ method: request.method(), path: url.pathname, status: response.status(), body })
            if (action === 'state') state = body
            return route.fulfill({ response }) // forwards the real router response, not a fabricated success
          }
          if (action === 'mark-read') state.last_read_timestamp = request.postDataJSON().timestamp
          if (action === 'clear') state.last_read_timestamp = state.last_cleared_timestamp = new Date().toISOString()
          const body = action === 'state' ? { ...state } : { success: true, ...state }
          exchanges.push({ method: request.method(), path: url.pathname, status: 200, body })
          return route.fulfill({ json: body })
        }
        const reply = syntheticReply(url.pathname + url.search, request.method())
        if (reply.status !== 200) unexpected.push(`${request.method()} ${url.pathname}`)
        return route.fulfill({ status: reply.status, json: reply.body })
      })
      const bell = page.locator('.app-header button[aria-controls="notification-panel"]')
      const panel = page.locator('#notification-panel')
      const item = (id: string) => panel.locator('.notification-item').filter({ has: page.getByRole('heading', { name: id, exact: true }) })
      async function open() {
        await bell.click()
        await expect(panel.locator('.notification-item')).toHaveCount(2)
      }
      async function checkpoint(name: string) {
        await page.screenshot({ path: testInfo.outputPath(`${name}.png`) })
        await writeFile(testInfo.outputPath(`${name}.json`), JSON.stringify({
          mode: routerUrl ? 'registered notification router + SQLite' : 'synthetic timestamp HTTP',
          url: page.url(), writes, state, exchanges,
          dom: await panel.innerText().catch(() => 'panel closed'),
          badge: await bell.locator('.badge').allTextContents(), errors, unexpected,
          geometry: await panel.evaluate(element => ({
            viewport: { width: innerWidth, height: innerHeight }, panel: element.getBoundingClientRect().toJSON(),
            actions: [...element.querySelectorAll('.notification-item button')].map(button => {
              const bounds = button.getBoundingClientRect()
              return { name: button.getAttribute('aria-label'), bounds: bounds.toJSON(),
                hit: button.contains(document.elementFromPoint(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)) }
            }),
          })),
        }, null, 2))
      }
      await page.goto('/streamers')
      await expect(bell).toBeVisible()
      await expect.poll(() => Boolean(peer)).toBe(true)
      await expect.poll(() => exchanges.length).toBeGreaterThan(0)
      const base = Math.max(Date.now() - 2000, Date.parse(state.last_cleared_timestamp || '1970-01-01') + 1,
        Date.parse(state.last_read_timestamp || '1970-01-01') + 1)
      const events = ['B', 'A'].map((id, index) => ({ type: 'notification_event', event_id: index + 1, data: {
        event_id: `989-${id}`, dedupe_key: `989-${id}`, title: id, body: `Synthetic local notice ${id}`,
        type: 'stream.online', severity: 'info', source: 'test', created_at: new Date(base + (1 - index)).toISOString(), target_url: '/videos',
      } }))
      events.forEach(event => peer!.send(JSON.stringify(event)))
      await expect(bell.locator('.badge')).toHaveText('2')
      await open()
      expect(writes).toEqual([])
      if (mobile) {
        const button = await item('B').getByRole('button', { name: 'Mark B read', exact: true }).boundingBox()
        expect(button!.height).toBeGreaterThanOrEqual(44)
        await item('B').getByRole('button', { name: 'Mark B read', exact: true }).tap()
      } else await item('B').getByRole('button', { name: 'Mark B read', exact: true }).click()
      await expect(bell.locator('.badge')).toHaveText('1')
      await expect(item('A')).toHaveClass(/unread/)
      await checkpoint('single-read')
      await panel.locator('.filter-menu-toggle').click()
      await panel.getByRole('button', { name: /^Unread/ }).click()
      await expect(panel.locator('.notification-item')).toHaveCount(1)
      await expect(item('A')).toBeVisible()
      await panel.locator('.filter-menu-toggle').click()
      await panel.getByRole('button', { name: /^All \d/ }).click()
      await page.reload()
      await open()
      await expect(item('B')).not.toHaveClass(/unread/)
      await expect(item('A')).toHaveClass(/unread/)
      await expect(panel).toContainText('local to this browser')
      events.forEach(event => peer!.send(JSON.stringify(event)))
      await expect(panel.locator('.notification-item')).toHaveCount(2)
      expect(writes).toEqual([])
      await item('B').getByRole('button', { name: 'Mark B unread', exact: true }).click()
      await expect(bell.locator('.badge')).toHaveText('2')
      await item('B').getByRole('button', { name: 'Open notification target for B' }).click()
      await expect(page).toHaveURL(/\/videos$/)
      await expect(bell.locator('.badge')).toHaveText('1')
      await open()
      await expect(item('A')).toHaveClass(/unread/)
      expect(writes).toEqual([])

      failure = 'mark-read'
      await panel.getByRole('button', { name: 'Mark all notifications read', exact: true }).click()
      await expect(panel).toContainText('could not be marked read')
      await expect(bell.locator('.badge')).toHaveText('1')
      failure = undefined
      await panel.getByRole('button', { name: 'Retry', exact: true }).click()
      await expect(item('A')).toBeVisible()
      await panel.getByRole('button', { name: 'Mark all notifications read', exact: true }).click()
      await expect(bell.locator('.badge')).toHaveCount(0)
      expect(writes).toEqual(['POST /api/notifications/mark-read', 'POST /api/notifications/mark-read'])
      await item('A').getByRole('button', { name: 'Mark A unread', exact: true }).click()
      await page.reload()
      await open()
      await expect(bell.locator('.badge')).toHaveText('1')
      await expect(item('A')).toHaveClass(/unread/)
      await expect(item('B')).not.toHaveClass(/unread/)
      await checkpoint('global-then-local-unread-reload')
      failure = 'state'
      await panel.getByRole('button', { name: 'Close notifications', exact: true }).click()
      await bell.click()
      await expect(panel).toContainText('could not be refreshed')
      await expect(bell.locator('.badge')).toHaveText('1')
      failure = undefined
      await panel.getByRole('button', { name: 'Retry', exact: true }).click()
      await expect(item('A')).toBeVisible()
      failure = 'clear'
      await panel.getByRole('button', { name: 'Clear all notifications', exact: true }).click()
      await expect(panel).toContainText('could not be cleared')
      await expect(bell.locator('.badge')).toHaveText('1')
      failure = undefined
      await panel.getByRole('button', { name: 'Retry', exact: true }).click()
      await expect(panel.locator('.notification-item')).toHaveCount(2)
      await panel.getByRole('button', { name: 'Clear all notifications', exact: true }).click()
      await expect(panel).toHaveCount(0)
      expect(writes).toEqual(['POST /api/notifications/mark-read', 'POST /api/notifications/mark-read', 'POST /api/notifications/clear', 'POST /api/notifications/clear'])
      await bell.click()
      await expect(panel).toContainText('All caught up')
      await checkpoint('cleared')
      expect(errors).toEqual([])
      expect(unexpected).toEqual([])
    })
  })
}
