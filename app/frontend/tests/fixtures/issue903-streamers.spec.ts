import { expect, test, type CDPSession, type Page } from '@playwright/test'
import { syntheticReply, syntheticStreamer } from './issue828SyntheticApi'

const origin = 'http://127.0.0.1:4184'
const streamers = Array.from({ length: 3 }, (_, index) => ({
  ...syntheticStreamer,
  id: index + 1,
  name: `synthetic_live_${index + 1}`,
  username: `synthetic_live_${index + 1}`,
  display_name: `Synthetic Live ${index + 1}`,
  is_live: true,
  title: 'Synthetic live title for neutral touch gestures',
  category_name: 'Synthetic category',
}))

async function installApi(page: Page) {
  const unexpected: string[] = []
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== origin) {
      unexpected.push(`External: ${url.origin}${url.pathname}`)
      return route.abort('blockedbyclient')
    }
    if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
    if (request.method() !== 'GET') {
      unexpected.push(`${request.method()} ${url.pathname}`)
      return route.fulfill({ status: 405, json: { detail: 'Read-only fixture' } })
    }
    if (['/api/streamers', '/api/status/streamers'].includes(url.pathname))
      return route.fulfill({ json: { streamers } })
    const profile = url.pathname.match(/^\/api\/streamers\/streamer\/(\d+)$/)
    if (profile) return route.fulfill({ json: streamers[Number(profile[1]) - 1] })
    if (/^\/api\/streamers\/\d+\/streams$/.test(url.pathname))
      return route.fulfill({ json: { streams: [] } })
    if (/^\/api\/videos\/\d+\/thumbnail$/.test(url.pathname))
      return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="90"><rect width="160" height="90" fill="black"/></svg>' })
    const reply = syntheticReply(url.pathname + url.search, request.method())
    if (reply.status !== 200) unexpected.push(`${url.pathname}: ${reply.status}`)
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  await page.routeWebSocket(/.*/, socket => socket.close({ code: 1000, reason: 'Synthetic REST-only fixture' }))
  return { unexpected, errors }
}

async function pan(cdp: CDPSession, page: Page, start: { x: number; y: number }, delta: { x: number; y: number }) {
  const touch = (x: number, y: number) => ({ x, y, id: 1, radiusX: 4, radiusY: 4, force: 1 })
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [touch(start.x, start.y)] })
  try {
    for (let step = 1; step <= 8; step++) {
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [touch(start.x + delta.x * step / 8, start.y + delta.y * step / 8)] })
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => resolve())))
    }
  } finally {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  }
}

for (const viewport of [{ width: 320, height: 640 }, { width: 390, height: 844 }, { width: 767, height: 1024 }]) {
  test(`native carousel pan and vertical scrolling work over cards at ${viewport.width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    const api = await installApi(page)
    await page.goto('/overview')
    const carousel = page.locator('.dashboard-card-grid')
    const cards = carousel.locator(':scope > .streamer-card')
    await expect(cards).toHaveCount(streamers.length)
    await cards.first().locator('.stream-title').evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }))
    await page.evaluate(() => document.fonts.ready)
    expect(await carousel.evaluate(element => element.scrollWidth > element.clientWidth)).toBe(true)
    const cdp = await page.context().newCDPSession(page)
    try {
      const point = async () => {
        // A following gesture must start after native inertia/snap settles,
        // not in a gap passing under a fixed coordinate between cards.
        await expect.poll(() => carousel.evaluate(async element => {
          const samples: number[] = []
          for (let frame = 0; frame < 5; frame++) {
            await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
            samples.push(element.scrollLeft)
          }
          return Math.max(...samples) - Math.min(...samples) < 0.25
        })).toBe(true)
        const candidate = await carousel.evaluate(element => {
          const port = element.getBoundingClientRect()
          return [...element.querySelectorAll('.stream-title')].map(title => {
            const box = title.getBoundingClientRect()
            const left = Math.max(box.left, port.left, 24)
            const right = Math.min(box.right, port.right, innerWidth - 24)
            return { x: right - 12, y: box.top + Math.min(12, box.height / 2), left, right }
          }).filter(box => box.right - box.left >= 64).sort((a, b) => b.right - a.right)[0]
        })
        expect(candidate, 'a visible neutral title is available as a touch origin').toBeTruthy()
        const { x, y } = candidate!
        const hit = await page.evaluate(({ x, y }) => {
          const element = document.elementFromPoint(x, y)
          return !!element?.closest('.streamer-card') && !element.closest('a, button')
        }, { x, y })
        expect(hit, 'gesture starts on neutral card content, not a link/overlay').toBe(true)
        return { x, y }
      }
      const initial = await carousel.evaluate(element => element.scrollLeft)
      const url = page.url()
      const firstPoint = await point()
      await pan(cdp, page, firstPoint, { x: -Math.min(180, firstPoint.x - 24), y: 0 })
      await expect.poll(() => carousel.evaluate(element => element.scrollLeft)).toBeGreaterThan(initial + 40)
      expect(page.url()).toBe(url)
      // Continue physically to the last card; never set scrollLeft or dispatch a wheel.
      for (let swipe = 0; swipe < 6; swipe++) {
        const start = await point()
        if (await carousel.evaluate(element => element.scrollWidth - element.clientWidth - element.scrollLeft < 2)) break
        await pan(cdp, page, start, { x: -Math.min(180, start.x - 24), y: 0 })
      }
      await expect.poll(() => carousel.evaluate(element => element.scrollWidth - element.clientWidth - element.scrollLeft)).toBeLessThan(2)
      const last = cards.last()
      const hit = await last.evaluate(element => {
        const box = element.getBoundingClientRect()
        const x = Math.min(innerWidth - 24, box.right - 24)
        const y = box.top + box.height / 2
        return element.contains(document.elementFromPoint(x, y))
      })
      expect(hit, 'last card is visibly hit-testable after swiping').toBe(true)
      const beforeVertical = await page.evaluate(() => ({ y: scrollY, max: document.documentElement.scrollHeight - innerHeight }))
      expect(beforeVertical.max, 'page has genuine vertical overflow').toBeGreaterThan(40)
      const down = beforeVertical.y > 40
      await pan(cdp, page, await point(), { x: 0, y: down ? 120 : -120 })
      if (down) await expect.poll(() => page.evaluate(() => scrollY)).toBeLessThan(beforeVertical.y - 20)
      else await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(beforeVertical.y + 20)
      expect(page.url()).toBe(url)
      await testInfo.attach('carousel-scroll', { body: JSON.stringify(await carousel.evaluate(element => ({ left: element.scrollLeft, width: element.clientWidth, scrollWidth: element.scrollWidth }))), contentType: 'application/json' })
      await page.screenshot({ path: testInfo.outputPath('streamer-carousel.png') })
      await last.getByRole('link', { name: 'View details', exact: true }).tap()
      await expect(page).toHaveURL(/\/streamers\/3$/)
      await expect(page.getByRole('heading', { name: 'Synthetic Live 3', exact: true, level: 1 })).toBeVisible()
      expect(api.unexpected).toEqual([])
      expect(api.errors).toEqual([])
    } finally {
      await cdp.detach()
    }
  })
}
