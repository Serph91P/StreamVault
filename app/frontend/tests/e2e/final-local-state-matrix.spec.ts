import { expect, test, type Page } from '@playwright/test'

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })

const notification = (index: number) => ({
  id: `matrix-${index}`,
  event_id: `matrix-${index}`,
  dedupe_key: `matrix-${index}`,
  type: index % 2 ? 'recording.failed' : 'recording.completed',
  severity: index % 2 ? 'error' : 'success',
  title: `Matrix notification ${index}`,
  body: `Synthetic state-matrix item ${index}`,
  timestamp: new Date(Date.UTC(2026, 9, 9, 12, 0, index % 60)).toISOString(),
  created_at: new Date(Date.UTC(2026, 9, 9, 12, 0, index % 60)).toISOString(),
  source: 'system',
  target_url: '/videos',
  actions: [],
  data: {},
  read: false,
})

async function seedNotifications(page: Page, count: number) {
  await page.addInitScript((items) => {
    localStorage.setItem('streamvault_notifications', JSON.stringify(items))
  }, Array.from({ length: count }, (_, index) => notification(index)))
}

async function selectSettingsSection(page: Page, section: string, accessibleName: RegExp) {
  const mobileSelect = page.getByLabel('Choose settings section')
  if (await mobileSelect.isVisible()) await mobileSelect.selectOption(section)
  else await page.getByRole('button', { name: accessibleName }).click()
}

test('Settings deep link retains dirty panel state and moves focus on section changes', async ({ page }) => {
  await page.route('**/api/twitch/connection-status', route => route.fulfill({
    json: { connected: false, valid: false, expires_at: null },
  }))
  await page.route('**/api/twitch/manual-token', route => route.fulfill({ json: { saved: true } }))
  await page.goto('/settings?section=twitch')
  const content = page.locator('.settings-content')
  await expect(page.getByRole('heading', { name: 'Twitch Connection' })).toBeVisible()
  await expect(content).toBeFocused()

  const token = page.getByLabel('Twitch OAuth token')
  await token.fill('unsaved-local-matrix-value')
  await selectSettingsSection(page, 'notifications', /^Notifications /)
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible()
  await expect(content).toBeFocused()

  await selectSettingsSection(page, 'twitch', /^Twitch Connection /)
  await expect(token).toHaveValue('unsaved-local-matrix-value')
  await page.getByRole('button', { name: 'Cancel' }).click()
  await expect(token).toHaveValue('')
  await token.fill('synthetic-local-browser-token')
  await page.getByRole('button', { name: 'Save token' }).click()
  await expect(token).toHaveValue('')
  await expect(page.getByText('Twitch OAuth token saved securely')).toBeVisible()

  await page.goto('/settings?section=notifications')
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible()
})

test('Settings lazy panel failure is visible, retryable, and restores panel focus', async ({ page }) => {
  let failed = false
  await page.route('**/assets/SettingsPanelHost-*.js', async route => {
    if (!failed) {
      failed = true
      await route.abort('failed')
      return
    }
    await route.continue()
  })
  await page.goto('/settings?section=notifications')
  await expect(page.getByRole('alert')).toContainText('could not be loaded')
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('heading', { name: 'Notifications', exact: true })).toBeVisible()
  await expect(page.locator('.settings-content')).toBeFocused()
})

test('notification 99+ badge, unread/error filters, clear action, and queue error state remain usable', async ({ page }) => {
  await seedNotifications(page, 100)
  await page.goto('/')
  const trigger = page.getByRole('button', { name: /Open notifications/ })
  await expect(trigger.locator('.badge')).toHaveText('99+')
  await trigger.click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('100 unread of 100 notifications')
  await dialog.getByRole('button', { name: /Filter/ }).click()
  await dialog.getByRole('button', { name: /Unread\s+100/ }).click()
  await expect(dialog).toContainText('100 unread of 100 notifications')
  await dialog.getByRole('button', { name: /Filter/ }).click()
  await dialog.getByRole('button', { name: /Errors\s+50/ }).click()
  await expect(dialog.getByText('Matrix notification 1', { exact: true })).toBeVisible()
  await expect(dialog.getByText('Matrix notification 2', { exact: true })).toHaveCount(0)

  await dialog.getByRole('button', { name: 'Clear all notifications' }).click()
  await expect(dialog).toBeHidden()
  await expect(trigger.locator('.badge')).toHaveCount(0)

  const queueTrigger = page.getByRole('button', { name: /Open background queue/ }).first()
  await queueTrigger.click()
  const queueDialog = page.getByRole('dialog')
  await expect(queueDialog).toContainText('Background queue updates are unavailable')
  await expect(queueDialog.getByRole('button', { name: 'Retry' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(queueTrigger).toBeFocused()
})