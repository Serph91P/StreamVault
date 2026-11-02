import { expect, test, type Locator, type Page } from '@playwright/test'

type Theme = 'dark' | 'light'
const widths = [320, 390, 1024, 1440] as const

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce', serviceWorkers: 'block' })

async function preparePage(page: Page, theme: Theme) {
  await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
  await page.route('**/auth/setup', route => route.fulfill({ json: { setup_required: false, welcome_completed: false } }))
  await page.route('**/api/twitch/connection-status', route => route.fulfill({ json: { connected: false } }))
  await page.route('**/api/recording/settings', route => route.fulfill({ json: {
    enabled: true,
    default_quality: 'best',
    filename_template: '{streamer}_{date}',
    filename_preset: 'default',
    use_chapters: true,
    use_category_as_chapter_title: true,
    supported_codecs: ['h264'],
    preferred_codec: 'h264',
    fallback_enabled: true,
  } }))
}

async function assertHeaderContainsUtilities(page: Page) {
  const header = page.locator('.app-header')
  await expect(header).toBeVisible()
  const bounds = await header.boundingBox()
  expect(bounds).not.toBeNull()
  const buttons = header.locator('.shell-utilities button:visible')
  expect(await buttons.count()).toBeGreaterThanOrEqual(4)
  for (const button of await buttons.all()) {
    const rect = await button.boundingBox()
    expect(rect).not.toBeNull()
    const label = await button.getAttribute('aria-label') || await button.innerText()
    expect(rect!.x, `${label} left edge`).toBeGreaterThanOrEqual(bounds!.x - 1)
    expect(rect!.y, `${label} top edge`).toBeGreaterThanOrEqual(bounds!.y - 1)
    expect(rect!.x + rect!.width, `${label} right edge`).toBeLessThanOrEqual(bounds!.x + bounds!.width + 1)
    expect(rect!.y + rect!.height, `${label} bottom edge`).toBeLessThanOrEqual(bounds!.y + bounds!.height + 1)
    expect(rect!.width, `${label} icon target width`).toBeGreaterThanOrEqual(47.9)
    expect(rect!.height, `${label} icon target height`).toBeGreaterThanOrEqual(47.9)
  }
}

async function assertSearchTextClearsIcon(page: Page) {
  const input = page.locator('.search-box .search-input')
  await input.fill('Ranked')
  const geometry = await input.evaluate(element => {
    const field = element as HTMLInputElement
    const style = getComputedStyle(field)
    const rect = field.getBoundingClientRect()
    const icon = field.parentElement!.querySelector(':scope > svg')!.getBoundingClientRect()
    return {
      value: field.value,
      textStart: rect.left + Number.parseFloat(style.borderLeftWidth) + Number.parseFloat(style.paddingLeft),
      iconRight: icon.right,
    }
  })
  expect(geometry.value).toBe('Ranked')
  expect(geometry.textStart, 'Entered search text must clear the leading icon').toBeGreaterThan(geometry.iconRight + 2)
  await input.clear()
}

async function assertTargets(controls: Locator, minimum: number) {
  for (const control of await controls.all()) {
    const rect = await control.boundingBox()
    expect(rect).not.toBeNull()
    expect(rect!.width).toBeGreaterThanOrEqual(minimum - 0.1)
    expect(rect!.height).toBeGreaterThanOrEqual(minimum - 0.1)
  }
}

async function assertNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(1)
}

for (const theme of ['light', 'dark'] as const) {
  for (const width of widths) {
    test(`browse controls remain readable and reachable at ${width}px in ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await preparePage(page, theme)
      await page.goto('/streamers')
      await expect(page.locator('.streamer-card').first()).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      await expect.poll(() => page.evaluate(() => document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark')).toBe(theme)
      await assertHeaderContainsUtilities(page)
      await assertSearchTextClearsIcon(page)

      const filters = page.locator('.filter-tabs button')
      await expect(filters).toHaveCount(4)
      for (const label of ['Alle', 'Live', 'Wird aufgenommen', 'Offline']) {
        const button = page.getByRole('button', { name: new RegExp(`^${label} \\d+$`) })
        await expect(button).toBeVisible()
        await expect(button.locator('.tab-badge')).toHaveText(/^\d+$/)
        const clipping = await button.evaluate(element => {
          const rect = element.getBoundingClientRect()
          const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT)
          const clippedText: string[] = []
          while (walker.nextNode()) {
            if (!walker.currentNode.textContent?.trim()) continue
            const range = document.createRange()
            range.selectNodeContents(walker.currentNode)
            for (const text of range.getClientRects()) {
              if (text.left < rect.left - 1 || text.right > rect.right + 1 || text.top < rect.top - 1 || text.bottom > rect.bottom + 1) {
                clippedText.push(walker.currentNode.textContent.trim())
              }
            }
          }
          return clippedText
        })
        expect(clipping, `${label} and its count must fit inside the filter`).toEqual([])
      }
      await assertTargets(filters, 44)
      await assertTargets(page.locator('.view-toggle button'), 48)
      await assertTargets(page.locator('.streamer-card .btn-more'), 48)
      await assertNoPageOverflow(page)

      await page.goto('/videos')
      await expect(page.locator('.video-card').first()).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      await assertHeaderContainsUtilities(page)
      await assertSearchTextClearsIcon(page)
      await assertTargets(page.locator('.view-toggle button'), 48)
      await assertTargets(page.locator('.filters-btn, .sort-control-wrap'), 44)
      const sortGeometry = await page.locator('.sort-value').evaluate(element => {
        const range = document.createRange()
        range.selectNodeContents(element)
        const label = element.parentElement!.getBoundingClientRect()
        const style = getComputedStyle(element.parentElement!)
        return {
          text: [...range.getClientRects()].map(rect => ({ left: rect.left, right: rect.right })),
          left: label.left + Number.parseFloat(style.paddingLeft),
          right: label.right - Number.parseFloat(style.paddingRight),
        }
      })
      for (const line of sortGeometry.text) {
        expect(line.left, 'Selected sort value must remain inside its control').toBeGreaterThanOrEqual(sortGeometry.left - 1)
        expect(line.right, 'Selected sort value must leave room for the chevron').toBeLessThanOrEqual(sortGeometry.right + 1)
      }
      await assertNoPageOverflow(page)
    })
  }

  test(`activity embeds the overview without a second page heading in ${theme}`, async ({ page }) => {
    await preparePage(page, theme)
    await page.goto('/activity')
    await expect(page.locator('.home-view .brief-headline')).toBeVisible()
    await expect(page.locator('h1:visible')).toHaveCount(1)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Aktivität')

    await page.goto('/overview')
    await expect(page.locator('h1:visible')).toHaveCount(1)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Übersicht')
    await expect(page.locator('.home-view .brief-headline')).toHaveCount(0)
  })
}
