import { expect, test } from '@playwright/test'
import { syntheticReply, syntheticStreamer } from './issue828SyntheticApi'

test('shared resource feedback keeps channel settings lazy', async ({ page }) => {
  const scripts: string[] = []
  page.on('request', request => {
    if (request.resourceType() === 'script') scripts.push(new URL(request.url()).pathname)
  })
  await page.routeWebSocket(/.*/, socket => socket.onMessage(() => {}))
  await page.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== 'http://127.0.0.1:4193') return route.abort('blockedbyclient')
    if (!/^\/(api|auth)\//.test(url.pathname)) return route.continue()
    const reply = syntheticReply(url.pathname, request.method())
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  await page.goto('/streamers')
  await expect(page.locator('.streamer-wrapper')).toHaveCount(1)
  expect(scripts.filter(path => /\/channel-settings-[^/]+\.js$/.test(path))).toEqual([])
})

for (const theme of ['light', 'dark']) for (const panel of [
  { trigger: /Open notifications/, title: 'Notifications' },
  { trigger: /Open background queue/, title: 'Background Queue' },
]) {
  test(`active backdrop closes ${panel.title} and restores focus ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
    await page.routeWebSocket(/.*/, socket => socket.onMessage(() => {}))
    await page.route('**/*', async route => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== 'http://127.0.0.1:4193') return route.abort('blockedbyclient')
      if (!/^\/(api|auth)\//.test(url.pathname)) return route.continue()
      const reply = syntheticReply(url.pathname, request.method())
      return route.fulfill({ status: reply.status, json: reply.body })
    })
    await page.goto('/')
    const trigger = page.getByRole('button', { name: panel.trigger }).first()
    await trigger.click()
    const dialog = page.getByRole('dialog', { name: panel.title, exact: true })
    await expect(dialog).toBeVisible()
    await expect.poll(() => dialog.evaluate(element => element.contains(document.activeElement))).toBe(true)
    expect(await page.locator('#app').evaluate(element => element.inert)).toBe(true)
    expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden')
    // Finish entry motion before proving that the pointer is outside the panel.
    await dialog.evaluate(element => Promise.all(element.getAnimations().map(animation => animation.finished)))
    const box = await dialog.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThan(5)
    await page.mouse.click(5, 500)
    await expect(dialog).toHaveCount(0)
    await expect(trigger).toBeFocused()
    expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
    expect(await page.locator('#app').evaluate(element => element.inert)).toBe(false)

    if (panel.title === 'Notifications') {
      const queueTrigger = page.getByRole('button', { name: /Open background queue/ }).first()
      await queueTrigger.click()
      const queue = page.getByRole('dialog', { name: 'Background Queue', exact: true })
      const queueClose = queue.getByRole('button', { name: 'Close background queue' })
      // The activity link is now the first control. Wait for initial autofocus
      // before choosing the nested dialog's restoration target.
      await expect(queue.getByRole('link', { name: 'Vollständige Aktivität' })).toBeFocused()
      await queueClose.focus()
      await expect(queueClose).toBeFocused()
      // Programmatically construct a stack; real users cannot reach the isolated shell.
      await page.getByRole('button', { name: /Open notifications/, includeHidden: true }).evaluate((element: HTMLElement) => element.click())
      await expect(dialog).toBeVisible()
      await expect(page.locator('[role="dialog"]')).toHaveCount(2)
      await expect(page.getByRole('dialog')).toHaveCount(1)
      expect(await page.locator('.queue-panel').evaluate(element => element.inert)).toBe(true)
      expect(await page.locator('.glass-popup-backdrop').first().evaluate(element => element.inert)).toBe(true)
      await dialog.evaluate(element => Promise.all(element.getAnimations().map(animation => animation.finished)))
      await page.mouse.click(5, 500)
      await expect(page.locator('[role="dialog"]')).toHaveCount(1)
      await expect(queue).toBeVisible()
      await expect(queueClose).toBeFocused()
      expect(await page.locator('.glass-popup-backdrop').evaluate(element => element.inert)).toBe(false)
      expect(await page.locator('#app').evaluate(element => element.inert)).toBe(true)
      expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden')
      await page.keyboard.press('Escape')
      await expect(page.locator('[role="dialog"]')).toHaveCount(0)
      await expect(queueTrigger).toBeFocused()
      expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
      expect(await page.locator('#app').evaluate(element => element.inert)).toBe(false)
    }
  })
}

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
    await page.getByText('Weitere Kanalaktionen', { exact: true }).click()
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
