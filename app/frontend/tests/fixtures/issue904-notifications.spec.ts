import { expect, test, type WebSocketRoute } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { syntheticReply } from './issue828SyntheticApi'
import { readyForSettledMotion } from './issue828Browser'

function syntheticEvents() {
  const noon = new Date()
  noon.setUTCHours(12, 0, 0, 0)
  return Array.from({ length: 24 }, (_, index) => ({
    type: 'notification_event', event_id: index + 1,
    data: {
      event_id: `synthetic-notification-${index}`, dedupe_key: `synthetic-notification-${index}`,
      type: 'stream.online', severity: index % 2 ? 'info' : 'warning', source: 'test',
      title: `Synthetic notice ${index + 1}`,
      body: 'Synthetic notification body with enough text to wrap on a narrow screen. No private content.',
      created_at: new Date(noon.getTime() - Math.floor(index / 8) * 86400000 - (index % 8) * 60000).toISOString(),
    },
  }))
}

for (const viewport of [{ width: 320, height: 640 }, { width: 390, height: 844 }, { width: 863, height: 900 }, { width: 1440, height: 900 }]) {
  test.describe(`notification scroll ${viewport.width}`, () => {
    test.use({ isMobile: viewport.width < 768, hasTouch: viewport.width < 768 })
    for (const theme of ['dark', 'light'] as const) {
      for (const expanded of [false, true]) {
        test(`day headers stay in flow ${theme} expanded=${expanded}`, async ({ page }, testInfo) => {
          await page.setViewportSize(viewport)
          await page.emulateMedia({ colorScheme: theme })
          const unexpected: string[] = []
          const writes: string[] = []
          const errors: string[] = []
          let peer: WebSocketRoute | undefined
          page.on('pageerror', error => errors.push(error.message))
          await page.routeWebSocket(/.*/, socket => {
            if (new URL(socket.url()).origin !== 'ws://127.0.0.1:4188') {
              unexpected.push('External WebSocket')
              return socket.close({ code: 1008, reason: 'Unexpected synthetic origin' })
            }
            peer = socket
            socket.onMessage(message => {
              if (String(message).includes('ping')) socket.send(JSON.stringify({ type: 'pong' }))
            })
          })
          await page.route('**/*', route => {
            const request = route.request()
            const url = new URL(request.url())
            if (url.origin !== 'http://127.0.0.1:4188') {
              unexpected.push(`External ${url.origin}${url.pathname}`)
              return route.abort('blockedbyclient')
            }
            if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
            if (request.method() !== 'GET') {
              writes.push(`${request.method()} ${url.pathname}`)
              if (request.method() === 'POST' && url.pathname === '/api/notifications/mark-read') {
                expect(request.postDataJSON()).toHaveProperty('timestamp')
                return route.fulfill({ json: { success: true } })
              }
            }
            const reply = syntheticReply(url.pathname + url.search, request.method())
            if (reply.status !== 200) unexpected.push(`${request.method()} ${url.pathname}`)
            return route.fulfill({ status: reply.status, json: reply.body })
          })
          await page.goto('/streamers')
          await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe(theme === 'light' ? 'light' : null)
          const bell = page.locator('.app-header button[aria-controls="notification-panel"]')
          await expect(bell).toBeVisible()
          await expect.poll(() => Boolean(peer)).toBe(true)
          const events = syntheticEvents()
          events.forEach(event => peer!.send(JSON.stringify(event)))
          await expect(bell.locator('.badge')).toHaveText(String(events.length))
          await bell.click()
          const panel = page.locator('#notification-panel')
          await readyForSettledMotion(panel)
          const toggle = panel.locator('.filter-menu-toggle')
          if (expanded) await toggle.click()
          const list = panel.locator('.notification-groups')
          await expect(list.locator('.notification-item')).toHaveCount(events.length)
          await expect(list.locator('.notification-group-header')).toHaveCount(3)
          const samples = []
          for (const delta of [0, 200, 450, -100, 1600, 20000, -10000]) {
            const box = (await list.boundingBox())!
            expect(box.height, 'cards retain a usable scroll viewport').toBeGreaterThan(44)
            await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
            if (delta) await page.mouse.wheel(0, delta)
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
            const state = await panel.evaluate(element => {
              const list = element.querySelector('.notification-groups')!
              const feed = element.querySelector('.notification-feed')!
              const filters = element.querySelector('.notification-filters')!
              const toggle = element.querySelector('.filter-menu-toggle')!
              const viewport = list.getBoundingClientRect()
              const headerNodes = [...list.querySelectorAll('.notification-group-header')]
              const cardNodes = [...list.querySelectorAll('.notification-item')]
              const headers = headerNodes.map(node => node.getBoundingClientRect())
              const cards = cardNodes.map(node => node.getBoundingClientRect())
              const overlaps = headers.flatMap((header, index) => cards.flatMap((card, cardIndex) => {
                const top = Math.max(header.top, card.top, viewport.top)
                const bottom = Math.min(header.bottom, card.bottom, viewport.bottom)
                return bottom > top + 1 ? [{ header: index, card: cardIndex, height: bottom - top }] : []
              }))
              const toggleBox = toggle.getBoundingClientRect()
              const filterHit = toggle.contains(document.elementFromPoint(toggleBox.x + toggleBox.width / 2, toggleBox.y + toggleBox.height / 2))
              const cardHits = cardNodes.flatMap((node, index) => {
                const card = cards[index]
                const top = Math.max(viewport.top, card.top)
                const bottom = Math.min(viewport.bottom, card.bottom)
                return bottom - top >= 4 ? [node.contains(document.elementFromPoint(card.x + card.width / 2, (top + bottom) / 2))] : []
              })
              const visible = [...headers, ...cards].filter(rect => rect.bottom > viewport.top && rect.top < viewport.bottom)
              const first = Math.min(...visible.map(rect => Math.max(viewport.top, rect.top)))
              const number = (value: string) => parseFloat(value) || 0
              const group = list.querySelector('.notification-group + .notification-group')!
              const groupList = list.querySelector('.notification-list')!
              const allowedGap = number(getComputedStyle(list).paddingTop) + number(getComputedStyle(group).marginTop)
                + number(getComputedStyle(groupList).paddingBottom) + Math.max(...cardNodes.map(node => number(getComputedStyle(node).marginBottom))) + 1
              return { listTop: list.scrollTop, feedTop: feed.scrollTop, viewport: viewport.toJSON(), filter: filters.getBoundingClientRect().toJSON(), overlaps, filterHit, cardHits, topGap: first - viewport.top, allowedGap }
            })
            samples.push(state)
            await writeFile(testInfo.outputPath('scroll-geometry.json'), JSON.stringify(samples, null, 2))
            await page.screenshot({ path: testInfo.outputPath(`scroll-${samples.length}.png`) })
            expect(state.overlaps, 'day header must not obscure notification-card content').toEqual([])
            expect(state.filterHit, 'filter remains hit-testable').toBe(true)
            expect(state.cardHits.length).toBeGreaterThan(0)
            expect(state.cardHits.every(Boolean), 'visible card content remains hit-testable').toBe(true)
            expect(state.topGap, 'no unexplained blank strip above the next content').toBeLessThanOrEqual(state.allowedGap)
            expect(state.feedTop, 'outer feed must not steal list scrolling').toBe(0)
            expect(state.filter.y).toBeCloseTo(samples[0].filter.y, 0)
          }
          expect(samples.some(sample => sample.listTop > 0)).toBe(true)
          if (viewport.width < 768) {
            const bounds = (await list.boundingBox())!
            const before = await list.evaluate(element => element.scrollTop)
            const cdp = await page.context().newCDPSession(page)
            const x = bounds.x + bounds.width / 2
            const startY = bounds.y + bounds.height * 0.8
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y: startY }] })
            for (let step = 1; step <= 6; step++) {
              await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x, y: startY - bounds.height * 0.6 * step / 6 }] })
              await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)))
            }
            await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
            await expect.poll(() => list.evaluate(element => element.scrollTop)).toBeGreaterThan(before)
            await cdp.detach()
          }
          expect(writes, 'opening and scrolling do not mark or clear data').toEqual([])
          if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click()
          await panel.getByRole('button', { name: /^Warnings/ }).click()
          await expect(list.locator('.notification-item')).toHaveCount(events.filter(event => event.data.severity === 'warning').length)
          const first = list.locator('.notification-item').first()
          await first.getByRole('button', { name: / read$/ }).click()
          await expect(first.getByRole('button', { name: / unread$/ })).toBeVisible()
          expect(writes, 'single-item read is local, not a global mutation').toEqual([])
          await panel.getByRole('button', { name: 'Mark all notifications read', exact: true }).click()
          await expect.poll(() => writes.length).toBe(1)
          expect(writes).toEqual(['POST /api/notifications/mark-read'])
          expect(unexpected).toEqual([])
          expect(errors).toEqual([])
        })
      }
    }
  })
}
