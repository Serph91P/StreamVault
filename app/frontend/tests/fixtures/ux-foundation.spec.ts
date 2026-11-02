import { expect, test } from '@playwright/test'
import { syntheticReply, syntheticStreamer } from './issue828SyntheticApi'

for (const width of [320, 390, 1440]) for (const theme of ['light', 'dark']) {
  test(`built foundation resource transitions ${width} ${theme}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
    let state = 'empty'
    let release!: () => void
    const loading = new Promise<void>(resolve => { release = resolve })
    await page.routeWebSocket(/.*/, socket => socket.onMessage(() => {}))
    await page.route('**/*', async route => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== 'http://127.0.0.1:4193') return route.abort('blockedbyclient')
      if (!/^\/(api|auth)\//.test(url.pathname)) return route.continue()
      if (url.pathname === '/api/streamers') {
        await loading
        if (state === 'offline') return route.abort('failed')
        if (state === 'forbidden') return route.fulfill({ status: 403, json: { detail: 'Synthetic access denied' } })
        if (state === 'error') return route.fulfill({ status: 503, json: { detail: 'Synthetic outage' } })
        return route.fulfill({ json: { streamers: state === 'empty' ? [] : [syntheticStreamer] } })
      }
      const reply = syntheticReply(url.pathname, request.method())
      return route.fulfill({ status: reply.status, json: reply.body })
    })
    await page.goto('/streamers')
    await expect(page.getByRole('status', { name: 'Kanäle werden geladen' })).toBeVisible()
    release()
    await expect(page.locator('[data-state="confirmed-empty"]')).toContainText('Noch keine Kanäle')
    state = 'fresh'
    await page.getByRole('button', { name: 'Kanalstatus erneut abrufen' }).click()
    await expect(page.locator('.streamer-wrapper')).toHaveCount(1)
    await page.getByLabel('Kanäle suchen', { exact: true }).fill('no-matching-channel')
    await expect(page.locator('[data-state="filter-empty"]')).toBeVisible()
    await page.getByRole('button', { name: 'Alle Kanäle anzeigen' }).click()
    state = 'error'
    await page.getByRole('button', { name: 'Kanalstatus erneut abrufen' }).click()
    await expect(page.locator('[data-state="stale"] time')).toBeVisible()
    const notice = page.locator('[data-state="stale"]')
    const title = await notice.locator('h2').boundingBox()
    const timestamp = await notice.locator('time').boundingBox()
    expect(timestamp!.x).toBeGreaterThanOrEqual(title!.x)
    await expect(page.locator('.streamer-wrapper')).toHaveCount(1)
    await page.screenshot({ path: testInfo.outputPath(`stale-${width}-${theme}.png`), fullPage: true })
    state = 'fresh'
    await page.getByRole('button', { name: 'Erneut versuchen' }).click()
    await expect(page.locator('[data-state="stale"]')).toHaveCount(0)
    for (state of ['forbidden', 'offline', 'error']) {
      await page.reload()
      await expect(page.locator(`[data-state="${state}"]`)).toBeVisible()
      await expect(page.locator('[data-state="confirmed-empty"]')).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Erneut versuchen' })).toBeVisible()
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
