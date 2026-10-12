import { expect, test, type Page } from '@playwright/test'

const routes = ['/', '/streamers', '/videos', '/settings', '/subscriptions', '/admin'] as const

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })

async function prepare(page: Page, theme: 'light' | 'dark') {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
  await page.route('**/auth/setup', route => route.fulfill({ json: { setup_required: false, welcome_completed: false } }))
  await page.route('**/api/twitch/connection-status', route => route.fulfill({ json: { connected: false } }))
}

async function expectOpaqueSurface(page: Page, selector: string) {
  const surface = page.locator(selector).first()
  await expect(surface).toBeVisible()
  await expect(surface).toHaveCSS('backdrop-filter', 'none')
  const background = await surface.evaluate(element => getComputedStyle(element).backgroundColor)
  expect(background).toMatch(/^rgb\(/)
}

test('R3 core routes use opaque in-flow surfaces without hover elevation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')

  for (const theme of ['light', 'dark'] as const) {
    await prepare(page, theme)
    await page.setViewportSize({ width: 1440, height: 900 })

    for (const route of routes) {
      await page.goto(route)
      await expect(page.locator('main.main-content')).toBeVisible()
      await expectOpaqueSurface(page, '.app-header')
      const card = page.locator('.glass-card, .surface-card, .base-panel').first()
      if (await card.count()) {
        await expectOpaqueSurface(page, '.glass-card, .surface-card, .base-panel')
        const hover = await card.evaluate(element => {
          const before = getComputedStyle(element).transform
          element.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }))
          return { before, after: getComputedStyle(element).transform }
        })
        expect(hover.after).toBe(hover.before)
      }
    }
  }
})

test('R3 queue and notification dialogs remain opaque and keyboard-closeable', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  await prepare(page, 'dark')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  await page.getByRole('button', { name: /Open background queue/ }).click()
  await expectOpaqueSurface(page, '.queue-panel')
  await page.keyboard.press('Escape')
  await expect(page.locator('.queue-panel')).toHaveCount(0)

  await page.getByRole('button', { name: /Open notifications/ }).click()
  await expectOpaqueSurface(page, '.notification-panel')
  await page.keyboard.press('Escape')
  await expect(page.locator('.notification-panel')).toHaveCount(0)
})
