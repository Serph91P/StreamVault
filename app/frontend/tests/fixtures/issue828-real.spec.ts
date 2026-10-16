import { expect, test, type Page } from '@playwright/test'
import { clickAndMeasureOrigin, installSyntheticApi, readyForMeasuredClick, readyForSettledMotion } from './issue828Browser'
import { chapterVariants, playerViewports, syntheticChapters } from './issue828SyntheticApi'

async function assertBounds(page: Page, hasChapters: boolean) {
  for (const name of ['Play', 'Mute', ...(hasChapters ? ['Chapters'] : []), 'Fullscreen', 'Back to previous page']) {
    const button = page.getByRole('button', { name, exact: true })
    await expect(button).toBeVisible()
    await readyForSettledMotion(button)
    const box = await button.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.y).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
    expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height)
    expect(box!.width).toBeGreaterThanOrEqual(43.9)
    expect(box!.height).toBeGreaterThanOrEqual(43.9)
  }
  await expect(page.getByRole('slider', { name: 'Video progress' })).toBeVisible()
  await expect(page.locator('.time-display')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
}

for (const viewport of playerViewports) {
  for (const variant of chapterVariants) {
    test(`REAL synthetic chapters ${variant} ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
      await page.setViewportSize(viewport)
      const api = await installSyntheticApi(page, variant)
      try {
        const loading = page.goto('/videos/1', { waitUntil: 'domcontentloaded' })
        await expect.poll(() => api.requests.includes('/api/videos/1/chapters')).toBe(true)
        await expect(page.getByText('Loading video player...', { exact: true })).toBeVisible()
        api.releaseChapters()
        await loading
        const video = page.locator('video.video-element')
        await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2)
        await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).duration)).toBe(12)
        const chapters = syntheticChapters(variant)
        await assertBounds(page, chapters.length > 0)
        const opener = page.getByRole('button', { name: 'Chapters', exact: true })
        if (!chapters.length) {
          await expect(opener).toHaveCount(0)
          await expect(page.getByRole('dialog', { name: 'Chapters' })).toHaveCount(0)
        } else {
          await opener.click()
          const dialog = page.getByRole('dialog', { name: 'Chapters' })
          await expect(dialog).toBeVisible()
          await expect(dialog).toBeFocused()
          await readyForSettledMotion(dialog)
          await expect(dialog.locator('.chapter-item')).toHaveCount(chapters.length)
          const box = await dialog.boundingBox()
          expect(box!.x).toBeGreaterThanOrEqual(0)
          expect(box!.y).toBeGreaterThanOrEqual(0)
          expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width)
          expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height)
          if (chapters.length === 1) expect(box!.height).toBeLessThan(250)
          const close = dialog.getByRole('button', { name: 'Close chapters', exact: true })
          const last = dialog.locator('.chapter-item').last()
          await readyForSettledMotion(close)
          await readyForSettledMotion(last)
          await page.keyboard.press('Tab')
          await expect(close).toBeFocused()
          await page.keyboard.press('Shift+Tab')
          await expect(last).toBeFocused()
          await page.keyboard.press('Tab')
          await expect(close).toBeFocused()
          if (variant === 'long') {
            // Genuine wheel scrolling inside the bounded chapter list, not fake
            // layout or a programmatically dispatched scroll success.
            await dialog.hover()
            await page.mouse.wheel(0, 100_000)
            await expect.poll(() => last.evaluate(el => {
              const rect = el.getBoundingClientRect()
              return el.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2))
            })).toBe(true)
            expect(await dialog.evaluate(el => el.scrollTop)).toBeGreaterThan(0)
          }
          await video.evaluate(el => { (el as HTMLVideoElement).currentTime = 6 })
          await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).seeking)).toBe(false)
          await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).currentTime)).toBe(6)
          await last.click()
          await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).currentTime)).toBe(chapters.at(-1)!.start)
          await expect.poll(() => video.evaluate(el => (el as HTMLVideoElement).seeking)).toBe(false)
          expect(await video.evaluate(el => (el as HTMLVideoElement).error)).toBeNull()
          await page.keyboard.press('Escape')
          await expect(dialog).toHaveCount(0)
          await expect(opener).toBeFocused()
          await opener.click()
          await close.click()
          await expect(dialog).toHaveCount(0)
          await expect(opener).toBeFocused()
          await opener.click()
          await readyForSettledMotion(dialog)
          const outside = await dialog.boundingBox()
          expect(outside!.x - 2).toBeGreaterThanOrEqual(0)
          expect(outside!.y - 2).toBeGreaterThanOrEqual(0)
          await page.mouse.click(outside!.x - 2, outside!.y - 2)
          await expect(dialog).toHaveCount(0)
          await expect(opener).toBeFocused()
          await page.getByRole('button', { name: 'Fullscreen', exact: true }).click()
          await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true)
          await opener.click()
          await expect(dialog).toBeVisible()
          await readyForSettledMotion(dialog)
          await dialog.locator('.chapter-item').first().click()
          await page.keyboard.press('Escape')
          await expect(dialog).toHaveCount(0)
          await expect(opener).toBeFocused()
          await page.getByRole('button', { name: 'Exit Fullscreen', exact: true }).click()
          await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false)
        }
        await page.screenshot({ path: testInfo.outputPath(`synthetic-${variant}-${viewport.width}x${viewport.height}.png`) })
        expect(api.unexpected).toEqual([])
      } finally { api.releaseChapters() }
    })
  }
}

test('REAL synthetic retry pill preserves routed mobile clearance', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const api = await installSyntheticApi(page, 'many')
  try {
    await page.goto('/add-streamer', { waitUntil: 'domcontentloaded' })
    const pill = page.locator('.mobile-connectivity-pill')
    const retry = pill.getByRole('button', { name: 'Retry', exact: true })
    const target = page.locator('main.main-content button:not([disabled])').last()
    await readyForSettledMotion(target)

    // The synthetic HTTP fixture stays real while closed WebSockets plus native
    // offline/online events move the app into its ordinary Retry state.
    for (let cycle = 0; cycle < 12 && await retry.count() === 0; cycle++) {
      await expect(pill).toBeVisible()
      await page.context().setOffline(true)
      await expect(pill).toContainText('Offline mode')
      await page.context().setOffline(false)
    }

    await expect(retry).toBeVisible()
    await target.scrollIntoViewIfNeeded()
    const [targetBox, pillBox] = await Promise.all([target.boundingBox(), pill.boundingBox()])
    expect(pillBox!.height).toBeGreaterThan(44)
    expect(pillBox!.y - (targetBox!.y + targetBox!.height)).toBeGreaterThanOrEqual(8)
    expect(await target.evaluate(element => {
      const rect = element.getBoundingClientRect()
      return element.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2))
    })).toBe(true)
    expect(api.unexpected).toEqual([])
  } finally {
    await page.context().setOffline(false)
    api.releaseChapters()
  }
})

// The actual Streamer detail History is the Videos tab. It does NOT expose a
// VideoCard link or Play overlay: StreamCard has Expand + Watch Recording.
// Exercise those real controls, never pretend that a nonexistent card navigates.
for (const viewport of playerViewports) {
  for (const entry of ['streamer-card', 'history-watch'] as const) {
    test(`REAL synthetic origin ${entry} ${viewport.width}x${viewport.height}`, async ({ page }) => {
      await page.setViewportSize(viewport)
      const api = await installSyntheticApi(page, 'many')
      api.releaseChapters()
      if (entry === 'streamer-card') {
        await page.goto('/streamers')
        await page.locator('.streamer-card').first().getByRole('link', { name: 'View details', exact: true }).click()
        await expect(page).toHaveURL(/\/streamers\/1$/)
        await page.getByRole('tab', { name: 'Videos', exact: true }).click()
      } else await page.goto('/streamers/1?tab=videos')
      await page.getByLabel('Sort streams', { exact: true }).selectOption('oldest')
      await expect.poll(() => new URL(page.url()).searchParams.get('sort')).toBe('oldest')
      const card = page.locator('#streamer-detail-previous-streams .stream-card').last()
      await card.getByRole('button', { name: 'Expand stream details' }).click()
      const watch = card.getByRole('button', { name: 'Watch Recording', exact: true })
      await readyForMeasuredClick(page, watch)
      const origin = new URL(page.url()).pathname + new URL(page.url()).search
      const title = await card.locator('.stream-title').textContent()
      const scroll = await clickAndMeasureOrigin(watch)
      expect(scroll).toBeGreaterThan(0)
      await expect(page).toHaveURL(/\/videos\/40$/)
      const back = page.getByRole('button', { name: 'Back to previous page' })
      const statusBanner = page.locator('.connectivity-banner')
      await expect(statusBanner).toHaveCount(1)
      await expect(statusBanner).toHaveAttribute('role', 'status')
      await expect(statusBanner).toContainText(/Reconnecting live updates|Live updates paused/)
      await expect(statusBanner).toBeVisible()
      await readyForMeasuredClick(page, back)
      expect(await page.locator('.connectivity-banner').evaluate((banner, backTop) =>
        banner.getBoundingClientRect().bottom <= backTop, (await back.boundingBox())!.y
      )).toBe(true)
      await back.click()
      await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe(origin)
      await expect(page.getByRole('tab', { name: 'Videos', exact: true })).toHaveAttribute('aria-selected', 'true')
      await expect(page.getByLabel('Sort streams', { exact: true })).toHaveValue('oldest')
      await expect(card).toHaveClass(/\bis-expanded\b/)
      await expect(card.getByRole('button', { name: 'Collapse stream details', exact: true })).toHaveAttribute('aria-expanded', 'true')
      await expect(card.locator('.stream-expanded')).toBeVisible()
      await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(scroll)
      await expect(card.locator('.stream-title')).toHaveText(title!)
      expect(api.unexpected).toEqual([])
    })
  }
}

for (const action of ['card', 'play'] as const) {
  test(`REAL synthetic Library streamer-filter ${action} origin`, async ({ page }) => {
    const api = await installSyntheticApi(page, 'default')
    api.releaseChapters()
    await page.goto('/videos?q=alpha&streamer=synthetic_alpha&sort=title&view=grid')
    const card = page.locator('.videos-container .video-card').last()
    await card.hover()
    const target = action === 'card' ? card.locator('.video-card-link') : card.getByRole('button', { name: /^Play / })
    await readyForMeasuredClick(page, target)
    const origin = page.url()
    const scroll = await clickAndMeasureOrigin(target)
    expect(scroll).toBeGreaterThan(0)
    await expect(page).toHaveURL(/\/streamer\/1\/stream\/40\/watch(?:\?|$)/)
    const back = page.getByRole('button', { name: 'Back to previous page' })
    const statusBanner = page.locator('.connectivity-banner')
    await expect(statusBanner).toHaveCount(1)
    await expect(statusBanner).toHaveAttribute('role', 'status')
    await expect(statusBanner).toContainText(/Reconnecting live updates|Live updates paused/)
    await expect(statusBanner).toBeVisible()
    await readyForMeasuredClick(page, back)
    expect(await page.locator('.connectivity-banner').evaluate((banner, backTop) =>
      banner.getBoundingClientRect().bottom <= backTop, (await back.boundingBox())!.y
    )).toBe(true)
    await back.click()
    await expect(page).toHaveURL(origin)
    await expect(page.getByPlaceholder('Search videos by title or streamer...')).toHaveValue('alpha')
    await expect(page.getByRole('combobox', { name: 'Filter videos by streamer', exact: true })).toHaveValue('synthetic_alpha')
    await expect(page.getByRole('combobox', { name: 'Sort videos', exact: true })).toHaveValue('title')
    await expect(page.getByRole('button', { name: 'Show videos as grid', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(scroll)
    expect(api.unexpected).toEqual([])
  })
}
