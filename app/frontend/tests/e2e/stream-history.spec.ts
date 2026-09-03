import { expect, test } from '@playwright/test'
import type { Locator, Page } from '@playwright/test'

const viewports = [
  { width: 360, height: 800, theme: 'light' },
  { width: 390, height: 844, theme: 'light' },
  { width: 768, height: 1024, theme: 'light' },
  { width: 1024, height: 768, theme: 'light' },
  { width: 1440, height: 900, theme: 'light' },
  { width: 1920, height: 1080, theme: 'light' },
  { width: 390, height: 844, theme: 'dark' },
  { width: 1440, height: 900, theme: 'dark' },
] as const

const longTitle = 'A deliberately long stream title that remains calm, readable, and clear without colliding with history controls'

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })

async function openHistory(page: Page, width: number, height: number, theme: string) {
  await page.setViewportSize({ width, height })
  await page.addInitScript(selectedTheme => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
  await page.goto('/streamers/1?tab=videos')
  await expect(page.getByRole('tab', { name: 'Videos' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: 'Stream History' })).toBeVisible()
  await expect(page.locator('.stream-card')).toHaveCount(4)
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
      .app-header, .bottom-nav, .sidebar-nav {
        visibility: hidden !important;
      }
    `,
  })

  await page.locator('.stream-title').first().evaluate((element, title) => {
    element.textContent = title
  }, longTitle)
}

async function expectMinimumTarget(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box, 'control should have a bounding box').not.toBeNull()
  expect(box!.width).toBeGreaterThanOrEqual(44)
  expect(box!.height).toBeGreaterThanOrEqual(44)
}

async function expectStableGeometry(page: Page, mobile: boolean) {
  const geometry = await page.evaluate(() => {
    const title = document.querySelector('.stream-title')!.getBoundingClientRect()
    const status = document.querySelector('.stream-status')!.getBoundingClientRect()
    const expand = document.querySelector('.expand-btn')!.getBoundingClientRect()
    const sort = document.querySelector('.sort-select')!
    const sortBox = sort.getBoundingClientRect()
    const sortIcon = document.querySelector('.select-icon')!.getBoundingClientRect()
    const tablist = document.querySelector('[role="tablist"]')!.getBoundingClientRect()
    const selected = document.querySelector('[role="tab"][aria-selected="true"]')!.getBoundingClientRect()
    return {
      documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      titleStatusOverlap: title.right > status.left && title.left < status.right && title.bottom > status.top && title.top < status.bottom,
      titleControlOverlap: title.right > expand.left && title.left < expand.right && title.bottom > expand.top && title.top < expand.bottom,
      sortIconClearsText: sortIcon.right <= sortBox.left + Number.parseFloat(getComputedStyle(sort).paddingLeft),
      selectedTabVisible: selected.left >= tablist.left - 1 && selected.right <= tablist.right + 1,
    }
  })

  expect(geometry).toEqual({
    documentOverflow: 0,
    titleStatusOverlap: false,
    titleControlOverlap: false,
    sortIconClearsText: true,
    selectedTabVisible: true,
  })

  await expectMinimumTarget(page.getByLabel('Sort streams'))
  await expectMinimumTarget(page.locator('.expand-btn').first())

  if (mobile) {
    const tabCue = await page.getByRole('tablist', { name: 'Streamer detail sections' }).evaluate(element => {
      element.scrollLeft = 0
      const list = element.getBoundingClientRect()
      const tabs = Array.from(element.querySelectorAll('[role="tab"]')).map(tab => tab.getBoundingClientRect())
      return {
        snap: getComputedStyle(element).scrollSnapType,
        overflows: element.scrollWidth > element.clientWidth,
        hasPartialTab: tabs.some(tab => tab.left < list.right && tab.right > list.right),
      }
    })
    expect(tabCue.snap).toContain('x')
    expect(tabCue.overflows).toBe(true)
    expect(tabCue.hasPartialTab).toBe(true)
  }
}

for (const viewport of viewports) {
  test(`${viewport.theme} stream history at ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop')
    test.setTimeout(60_000)
    await openHistory(page, viewport.width, viewport.height, viewport.theme)
    await expectStableGeometry(page, viewport.width <= 390)

    const panel = page.locator('#streamer-detail-panel-videos')
    const snapshotPrefix = `stream-history-${viewport.theme}-${viewport.width}x${viewport.height}`
    await expect(panel).toHaveScreenshot(`${snapshotPrefix}-collapsed.png`, {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    })

    await page.locator('.expand-btn').first().click()
    await expect(page.locator('.stream-expanded')).toHaveCount(1)
    await expect(page.locator('.stream-title').first()).toHaveText(longTitle)
    for (const control of await page.locator('.stream-expanded button').all()) {
      await expectMinimumTarget(control)
    }
    await expect(panel).toHaveScreenshot(`${snapshotPrefix}-expanded.png`, {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
    })
  })
}

test('stream history reflows at 450 CSS pixels', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  await openHistory(page, 450, 900, 'light')

  const reflow = await page.locator('#streamer-detail-panel-videos').evaluate(panel => ({
    documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    panelOverflow: panel.scrollWidth - panel.clientWidth,
    panelWidth: panel.getBoundingClientRect().width,
  }))
  expect(reflow.documentOverflow).toBe(0)
  expect(reflow.panelOverflow).toBe(0)
  expect(reflow.panelWidth).toBeLessThanOrEqual(450)
})
