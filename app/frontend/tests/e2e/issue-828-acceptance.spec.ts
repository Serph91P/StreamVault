import { expect, test, type Locator, type Page } from '@playwright/test'
import { localSeekMedia } from '../fixtures/media/issue828Media'
import { clickAndMeasureOrigin, readyForMeasuredClick } from '../fixtures/issue828Browser'

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 640 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
] as const

async function expectVisibleTarget(locator: Locator, page: Page) {
  await expect(locator).toBeVisible()
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height)
  expect(box!.width).toBeGreaterThanOrEqual(43.9)
  expect(box!.height).toBeGreaterThanOrEqual(43.9)
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
}

test('issue 828 keeps the Admin header and live titles readable across the required viewport matrix', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  test.setTimeout(90_000)

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.goto('/admin', { waitUntil: 'domcontentloaded' })
    const header = page.locator('.page-header')
    const back = header.getByRole('link', { name: 'Back to System' })
    const title = header.getByRole('heading', { name: 'Admin' })
    const subtitle = header.locator('.page-header-subtitle')
    const status = header.getByText('Admin tools', { exact: true })

    await expectVisibleTarget(back, page)
    await expect(title).toBeVisible()
    await expect(subtitle).toBeVisible()
    await expect(status).toBeVisible()
    const headerGeometry = await header.evaluate(element => {
      const title = element.querySelector('.page-header-title-text')!.getBoundingClientRect()
      const subtitle = element.querySelector('.page-header-subtitle')!.getBoundingClientRect()
      const status = element.querySelector('.diag-status')!.getBoundingClientRect()
      return {
        titleWidth: title.width,
        subtitleWidth: subtitle.width,
        copyWidth: element.querySelector('.page-header-copy')!.getBoundingClientRect().width,
        groupWidth: element.querySelector('.page-header-title-group')!.getBoundingClientRect().width,
        subtitleDisplay: getComputedStyle(element.querySelector('.page-header-subtitle')!).display,
        statusWidth: status.width,
        subtitleBelowTitle: subtitle.top >= title.top,
      }
    })
    expect(headerGeometry.titleWidth).toBeGreaterThan(40)
    expect(headerGeometry.subtitleWidth, `header at ${viewport.width}px: ${JSON.stringify(headerGeometry)}`).toBeGreaterThan(120)
    expect(headerGeometry.statusWidth).toBeGreaterThan(70)
    expect(headerGeometry.subtitleBelowTitle).toBe(true)
    await expectNoHorizontalOverflow(page)
    await page.screenshot({ path: testInfo.outputPath(`issue-828-admin-${viewport.width}.png`), fullPage: true, animations: 'disabled' })

    await page.goto('/', { waitUntil: 'domcontentloaded' })
    const liveTitle = page.locator('.streamer-card.is-live .stream-title').first()
    await expect(liveTitle).toBeVisible()
    await liveTitle.evaluate(element => {
      element.textContent = 'Synthetic live title with descenders gypq and enough words to exercise the complete three-line clamp without clipped glyph fragments'
    })
    const liveGeometry = await liveTitle.evaluate(element => {
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      const range = document.createRange()
      range.selectNodeContents(element)
      const lineRects = Array.from(range.getClientRects())
      const visibleLines = lineRects.filter(line => line.top < rect.bottom - Number.parseFloat(style.paddingBottom))
      return {
        // Keep the clipping checks intact. These numeric observations distinguish
        // empty text, transient layout/transform and a genuinely clipped line.
        textLength: element.textContent?.length ?? 0,
        connected: element.isConnected,
        top: rect.top,
        bottom: rect.bottom,
        height: rect.height,
        fontSize: style.fontSize,
        display: style.display,
        transform: style.transform,
        paddingBottomCss: style.paddingBottom,
        lineRects: lineRects.map(line => ({ top: line.top, bottom: line.bottom, height: line.height, width: line.width })),
        ancestors: [element.parentElement, element.parentElement?.parentElement, element.closest('.streamer-card')].map(parent => {
          if (!parent) return null
          const box = parent.getBoundingClientRect()
          const css = getComputedStyle(parent)
          return { top: box.top, bottom: box.bottom, height: box.height, overflow: css.overflow, transform: css.transform }
        }),
        visibleLineCount: visibleLines.length,
        clippedVisibleLine: visibleLines.some(line => line.bottom > rect.bottom - Number.parseFloat(style.paddingBottom) + 1),
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        lineHeight: Number.parseFloat(style.lineHeight),
        paddingBottom: Number.parseFloat(style.paddingBottom),
        left: rect.left,
        right: rect.right,
      }
    })
    await testInfo.attach(`live-title-geometry-${viewport.width}`, { body: JSON.stringify(liveGeometry), contentType: 'application/json' })
    expect(liveGeometry.right).toBeLessThanOrEqual(viewport.width)
    expect(liveGeometry.left).toBeGreaterThanOrEqual(0)
    expect(liveGeometry.lineHeight).toBeGreaterThan(0)
    expect(liveGeometry.visibleLineCount, `live title at ${viewport.width}px: ${JSON.stringify(liveGeometry)}`).toBeGreaterThan(0)
    expect(liveGeometry.clippedVisibleLine, 'no partially cut visible text line').toBe(false)
    expect(liveGeometry.clientHeight).toBeGreaterThan(0)
    expect(liveGeometry.right - liveGeometry.left).toBeLessThanOrEqual(viewport.width)
    await expect(page.locator('.streamer-card.is-live .status-row').first()).toBeVisible()
    await expect(page.locator('.streamer-card.is-live .stat-category').first()).toBeVisible()
    await expectNoHorizontalOverflow(page)
    await page.screenshot({ path: testInfo.outputPath(`issue-828-live-title-${viewport.width}.png`), fullPage: true, animations: 'disabled' })
  }
})

test('issue 828 preserves the actual Overview card and Play origin', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/videos/*/stream', localSeekMedia)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  const overviewCard = page.locator('.dashboard-video-grid .video-card-link').first()
  await expect(overviewCard).toBeVisible()
  await overviewCard.click()
  await expect(page).toHaveURL(/\/streamer\/1\/stream\/1\/watch(?:\?|$)/)
  await page.getByRole('button', { name: 'Back to previous page' }).click()
  await expect(page).toHaveURL(/\/$/)

  const playCard = page.locator('.dashboard-video-grid .video-card').first()
  await playCard.hover()
  await playCard.getByRole('button', { name: /^Play / }).click()
  await expect(page).toHaveURL(/\/videos\/1(?:\?|$)/)
  await page.getByRole('button', { name: 'Back to previous page' }).click()
  await expect(page).toHaveURL(/\/$/)

  await expectNoHorizontalOverflow(page)
  await page.screenshot({ path: testInfo.outputPath('issue-828-origin-return.png'), fullPage: true, animations: 'disabled' })
})

test('issue 828 preserves Library Play search/filter/sort/grid and measured scroll', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/videos/*/stream', localSeekMedia)
  await page.goto('/videos?q=alpha&streamer=streamer_alpha&sort=title&view=list')
  await page.getByRole('button', { name: 'Show videos as grid', exact: true }).click()
  const card = page.locator('.videos-container .video-card').last()
  await card.scrollIntoViewIfNeeded()
  await card.hover()
  const play = card.getByRole('button', { name: /^Play / })
  await readyForMeasuredClick(page, play)
  const origin = page.url()
  const originScroll = await clickAndMeasureOrigin(play)
  expect(originScroll).toBeGreaterThan(0)
  await expect(page).toHaveURL(/\/streamer\/\d+\/stream\/\d+\/watch(?:\?|$)/)
  await page.getByRole('button', { name: 'Back to previous page' }).click()
  await expect.poll(() => page.evaluate(() => {
    const url = new URL(location.href)
    return [url.pathname, ...['q', 'streamer', 'sort', 'view'].map(key => url.searchParams.get(key))]
  })).toEqual(['/videos', 'alpha', 'streamer_alpha', 'title', 'grid'])
  await expect(page).toHaveURL(origin)
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(originScroll)
  await expect(page.getByPlaceholder('Search videos by title or streamer...')).toHaveValue('alpha')
  await expect(page.getByRole('combobox', { name: 'Filter videos by streamer', exact: true })).toHaveValue('streamer_alpha')
  await expect(page.getByRole('combobox', { name: 'Sort videos', exact: true })).toHaveValue('title')
  await expect(page.getByRole('button', { name: 'Show videos as grid', exact: true })).toHaveAttribute('aria-pressed', 'true')
})

test('issue 828 direct entry and reload use a safe fallback, ignoring external origin input', async ({ context }) => {
  // Fresh pages have no fabricated history state and no in-app previous route.
  for (const reload of [false, true]) {
    const page = await context.newPage()
    await page.route('**/api/videos/*/stream', localSeekMedia)
    await page.goto('/videos/1?origin=https%3A%2F%2Fexample.invalid&scroll=999')
    if (reload) await page.reload()
    await page.getByRole('button', { name: 'Back to previous page' }).click()
    await expect(page).toHaveURL(/\/videos$/)
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
    await page.close()
  }
})
