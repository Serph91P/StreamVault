import { expect, test, type Page } from '@playwright/test'
import { installSyntheticApi, readyForMeasuredClick, readyForSettledMotion } from './issue828Browser'
import { longClockMedia } from './media/issue894Media'

async function openPlayer(page: Page, chapters: 'default' | 'long' = 'default') {
  const api = await installSyntheticApi(page, chapters)
  api.releaseChapters()
  await page.route('**/api/videos/*/stream', longClockMedia)
  await page.goto('/videos/1', { waitUntil: 'domcontentloaded' })
  const video = page.locator('video.video-element')
  await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2)
  await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).duration)).toBe(50400)
  return { api, video }
}

for (const viewport of [
  { width: 320, height: 640 }, { width: 360, height: 640 },
  { width: 390, height: 844 }, { width: 430, height: 932 },
  { width: 568, height: 320 },
]) {
  test(`long recording has compact, fully usable controls at ${viewport.width}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    const { api, video } = await openPlayer(page)
    // Native media seeking, not a fabricated duration or synthetic canplay event.
    await video.evaluate(el => { (el as HTMLVideoElement).currentTime = 39600 })
    await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).seeking)).toBe(false)
    await expect(page.locator('.time-display')).toContainText('11:00:00')
    await expect(page.locator('.time-display')).toContainText('14:00:00')
    await expect(page.locator('.loading-overlay')).toHaveCount(0)
    await page.locator('.video-wrapper').scrollIntoViewIfNeeded()
    const bounds = await page.locator('.video-wrapper').boundingBox()
    const geometry = []
    for (const name of ['Play', 'Mute', 'Chapters', 'Fullscreen']) {
      const button = page.getByRole('button', { name, exact: true })
      await readyForSettledMotion(button)
      const box = (await button.boundingBox())!
      const icon = (await button.locator('svg').boundingBox())!
      geometry.push({ name, box, icon })
      expect(box.width, `${name} touch width`).toBeGreaterThanOrEqual(43.9)
      expect(box.height, `${name} touch height`).toBeGreaterThanOrEqual(43.9)
      expect(box.width, `${name} stays compact`).toBeLessThanOrEqual(48)
      expect(box.height, `${name} stays compact`).toBeLessThanOrEqual(48)
      expect(box.x).toBeGreaterThanOrEqual(bounds!.x - 1)
      expect(box.x + box.width).toBeLessThanOrEqual(bounds!.x + bounds!.width + 1)
      expect(box.y + box.height).toBeLessThanOrEqual(bounds!.y + bounds!.height + 1)
      expect(icon.width, `${name} compact icon`).toBeLessThanOrEqual(24)
      expect(icon.height, `${name} compact icon`).toBeLessThanOrEqual(24)
      const hits = await button.evaluate(el => {
        const r = el.getBoundingClientRect()
        return [[.5, .5], [.1, .5], [.9, .5], [.5, .1], [.5, .9]].map(([x, y]) => {
          const hit = document.elementFromPoint(r.x + r.width * x, r.y + r.height * y)
          return { inside: el.contains(hit), hit: hit?.getAttribute('class'), y: r.y, h: r.height }
        })
      })
      expect(hits.every(hit => hit.inside), `${name} is not clipped by its control group`).toBe(true)
    }
    const clockFits = await page.locator('.time-display').evaluate(el => {
      const parent = el.getBoundingClientRect()
      return [...el.children].filter(child => child.getClientRects().length).every(child => {
        const r = child.getBoundingClientRect()
        return r.left >= parent.left - 1 && r.right <= parent.right + 1
      })
    })
    expect(clockFits, 'long timestamps fit their allocated space').toBe(true)
    await expect(page.getByRole('slider', { name: 'Video progress' })).toBeVisible()
    expect(await video.evaluate(el => (el as HTMLVideoElement).error)).toBeNull()
    expect(api.unexpected).toEqual([])
    await testInfo.attach('control-geometry', {
      body: JSON.stringify({ viewport, geometry }), contentType: 'application/json',
    })
    await page.screenshot({ path: testInfo.outputPath(`long-clock-${viewport.width}.png`) })
  })
}

for (const width of [360, 390]) {
  for (const variant of ['default', 'long'] as const) {
    test(`chapter opening and closing preserves document scroll ${width} ${variant}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 640 })
      const { api } = await openPlayer(page, variant)
      const opener = page.getByRole('button', { name: 'Chapters', exact: true })
      const before = await readyForMeasuredClick(page, opener)
      expect(before).toBeGreaterThan(0)
      const probe = await page.evaluateHandle(() => {
        const start = scrollY
        const deltas: number[] = []
        const observe = () => deltas.push(scrollY - start)
        addEventListener('scroll', observe)
        return { deltas, cleanup: () => removeEventListener('scroll', observe) }
      })
      try {
        const point = (await opener.boundingBox())!
        await page.touchscreen.tap(point.x + point.width / 2, point.y + point.height / 2)
        const dialog = page.getByRole('dialog', { name: 'Chapters' })
        await readyForSettledMotion(dialog)
        await expect(dialog).toBeFocused()
        expect(await page.evaluate(() => scrollY)).toBe(before)
        if (variant === 'long') {
          const panel = (await dialog.boundingBox())!
          await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2)
          await page.mouse.wheel(0, 100_000)
          await expect.poll(() => dialog.evaluate(el =>
            Math.abs(el.scrollTop - (el.scrollHeight - el.clientHeight)))).toBeLessThanOrEqual(1)
          expect(await dialog.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
          // A real extra wheel at the list boundary must not chain into the page.
          await page.mouse.wheel(0, 400)
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
          expect(await page.evaluate(() => scrollY)).toBe(before)
        }
        await page.keyboard.press('Escape')
        await expect(dialog).toHaveCount(0)
        await expect(opener).toBeFocused()
        expect(await page.evaluate(() => scrollY)).toBe(before)
        // Enter is dispatched from the genuinely restored opener focus.
        await page.keyboard.press('Enter')
        await readyForSettledMotion(dialog)
        expect(await page.evaluate(() => scrollY)).toBe(before)
        await dialog.getByRole('button', { name: 'Close chapters' }).tap()
        await expect(dialog).toHaveCount(0)
        await expect(opener).toBeFocused()
        expect(await page.evaluate(() => scrollY)).toBe(before)
        expect(await probe.evaluate(p => p.deltas.every(delta => Math.abs(delta) <= 1)),
          'opening/closing must not even briefly move the page').toBe(true)
      } finally {
        await probe.evaluate(p => p.cleanup())
        await probe.dispose()
      }
      expect(api.unexpected).toEqual([])
    })
  }
}
