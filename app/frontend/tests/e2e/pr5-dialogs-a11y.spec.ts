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

  const controls = dialog.locator([
    'a[href]:visible',
    'button:not([disabled]):visible',
    'input:not([disabled]):not([type="hidden"]):visible',
    'select:not([disabled]):visible',
    'textarea:not([disabled]):visible',
    '[tabindex]:not([tabindex="-1"]):visible',
  ].join(','))

  // The trap resolves its boundary live on every keydown. Exercise that contract
  // while notification controls may still be hydrating: focus may advance to a
  // newly inserted control, but it must never escape the active dialog.
  await controls.last().focus()
  await page.keyboard.press('Tab')
  expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true)

  if (await dialog.getByRole('heading', { name: 'Notifications' }).count()) {
    await expect(dialog.getByText('Recording ready', { exact: true })).toBeVisible()
  }

  const isQueueDialog = Boolean(await dialog.getByRole('heading', { name: 'Background Queue' }).count())
  if (isQueueDialog) {
    const queueLoading = dialog.getByText('Loading background jobs…', { exact: true })
    await expect(dialog.getByText('Background queue updates are unavailable.', { exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: 'Retry' }).click()
    await expect(queueLoading).toBeVisible()

    // Retry deliberately changes the tabbable set from Close-only to Close + Retry.
    // Capture strict boundaries only after that existing mock response has settled.
    await expect(queueLoading).toBeHidden()
    await expect(dialog.getByText('Background queue updates are unavailable.', { exact: true })).toBeVisible()
  }

  // Once the async content is present, snapshot the actual boundary elements and
  // prove both wrap directions rather than comparing against mutable locators.
  const boundaryElements = await controls.elementHandles()
  expect(boundaryElements.length).toBeGreaterThan(0)
  const firstBoundary = boundaryElements[0]!
  const lastBoundary = boundaryElements.at(-1)!

  const boundaryState = async () => firstBoundary.evaluate((first, last) => {
    const active = document.activeElement
    const label = (node: Node | null) => node instanceof Element
      ? node.getAttribute('aria-label') || node.textContent?.trim() || null
      : null
    return {
      first: label(first),
      last: label(last),
      active: label(active),
      firstConnected: first.isConnected,
      lastConnected: last.isConnected,
      sameBoundary: first === last,
      activeIsFirst: active === first,
      activeIsLast: active === last,
    }
  }, lastBoundary)

  await lastBoundary.focus()
  await page.keyboard.press('Tab')
  const forwardState = await boundaryState()
  expect(forwardState.activeIsFirst, JSON.stringify(forwardState)).toBe(true)

  await firstBoundary.focus()
  await page.keyboard.press('Shift+Tab')
  const backwardState = await boundaryState()
  expect(backwardState.activeIsLast, JSON.stringify(backwardState)).toBe(true)

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
