import { expect, test } from '@playwright/test'
import axe from 'axe-core'
import type { Locator, Page } from '@playwright/test'

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })

async function seedNotifications(page: Page, theme: 'dark' | 'light' = 'light') {
  await page.addInitScript(({ selectedTheme }) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
    localStorage.setItem('streamvault_notifications', JSON.stringify([
      {
        id: 'evt-pr5',
        event_id: 'evt-pr5',
        dedupe_key: 'evt-pr5',
        type: 'recording.completed',
        severity: 'success',
        title: 'Recording ready',
        body: 'A deterministic recording completed successfully.',
        timestamp: '2026-09-03T12:00:00.000Z',
        created_at: '2026-09-03T12:00:00.000Z',
        source: 'system',
        target_url: '/videos/1',
        actions: [],
        data: {},
        read: false,
      },
    ]))
  }, { selectedTheme: theme })
}

async function expectMinimumTarget(locator: Locator) {
  const box = await locator.boundingBox()
  expect(box).not.toBeNull()
  expect(box!.width).toBeGreaterThanOrEqual(43.9)
  expect(box!.height).toBeGreaterThanOrEqual(43.9)
}

async function expectDialogLifecycle(page: Page, trigger: Locator) {
  await trigger.click()
  const dialog = page.getByRole('dialog').last()
  await expect(dialog).toBeVisible()
  await expect(dialog).toContainText(/Notifications|Background Queue/)
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true)
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden')

  const controls = dialog.locator('button:not([disabled]):visible, a[href]:visible, input:not([disabled]):visible, select:not([disabled]):visible, textarea:not([disabled]):visible')
  const count = await controls.count()
  await controls.last().focus()
  await page.keyboard.press('Tab')
  await expect(controls.first()).toBeFocused()
  await controls.first().focus()
  await page.keyboard.press('Shift+Tab')
  await expect(controls.nth(count - 1)).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
}

test('notification and queue overlays trap focus, close, and restore triggers', async ({ page }) => {
  await seedNotifications(page)
  await page.goto('/')
  await expectDialogLifecycle(page, page.getByRole('button', { name: /Open notifications/ }))
  await expectDialogLifecycle(page, page.getByRole('button', { name: /Open background queue/ }).first())
})

test('stacked overlays retain the shared body lock and close topmost first', async ({ page }) => {
  await seedNotifications(page)
  await page.goto('/')
  const notificationTrigger = page.getByRole('button', { name: /Open notifications/ })
  const queueTrigger = page.getByRole('button', { name: /Open background queue/ }).first()
  await notificationTrigger.click()
  await queueTrigger.evaluate((element: HTMLElement) => element.click())
  const dialogs = page.locator('[role="dialog"]')
  await expect(dialogs).toHaveCount(2)

  await page.keyboard.press('Escape')
  await expect(dialogs).toHaveCount(1)
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('hidden')
  await expect(dialogs).toContainText('Notifications')

  await page.keyboard.press('Escape')
  await expect(dialogs).toHaveCount(0)
  expect(await page.evaluate(() => document.body.style.overflow)).toBe('')
})

test('shell and Admin queue entry points have unique dialog relationships', async ({ page }) => {
  await page.goto('/admin')
  const triggers = page.getByRole('button', { name: /Open background queue/ })
  await expect(triggers).toHaveCount(2)
  await triggers.nth(0).click()
  await triggers.nth(1).evaluate((element: HTMLElement) => element.click())

  const ids = await page.locator('[role="dialog"]').evaluateAll(dialogs => dialogs.map(dialog => ({
    id: dialog.id,
    labelledBy: dialog.getAttribute('aria-labelledby'),
  })))
  expect(new Set(ids.map(item => item.id)).size).toBe(2)
  expect(new Set(ids.map(item => item.labelledBy)).size).toBe(2)
})

for (const theme of ['light', 'dark'] as const) {
  test(`notifications ${theme} visual and full Axe scan`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop')
    await page.setViewportSize({ width: 390, height: 844 })
    await seedNotifications(page, theme)
    await page.goto('/')
    await page.getByRole('button', { name: /Open notifications/ }).click()
    const dialog = page.getByRole('dialog')
    for (const control of await dialog.locator('button:not([disabled]):visible').all()) {
      await expectMinimumTarget(control)
    }
    await page.addScriptTag({ content: axe.source })
    const violations = await page.evaluate(async () => {
      const result = await (window as typeof window & { axe: typeof axe }).axe.run(document)
      return result.violations.filter(violation => violation.impact === 'serious' || violation.impact === 'critical')
    })
    expect(violations).toEqual([])
    await expect(page).toHaveScreenshot(`notifications-${theme}-390.png`, {
      animations: 'disabled',
      caret: 'hide',
      mask: [page.locator('img, video, time')],
      maxDiffPixels: 600,
      scale: 'css',
    })
  })
}
