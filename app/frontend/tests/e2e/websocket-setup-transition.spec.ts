import { expect, test } from '@playwright/test'

test('uses the realtime socket contract configured for setup and logout', async ({ page }, testInfo) => {
  const useMockData = testInfo.project.metadata.useMockData
  expect(typeof useMockData).toBe('boolean')

  await page.addInitScript(() => {
    class ObservedWebSocket extends EventTarget {
      static readonly CONNECTING = 0
      static readonly OPEN = 1
      static readonly CLOSING = 2
      static readonly CLOSED = 3
      static urls: string[] = []

      readyState = ObservedWebSocket.CONNECTING
      constructor(url: string) {
        super()
        ObservedWebSocket.urls.push(url)
        queueMicrotask(() => {
          this.readyState = ObservedWebSocket.OPEN
          this.dispatchEvent(new Event('open'))
        })
      }
      close() {
        if (this.readyState === ObservedWebSocket.CLOSED) return
        this.readyState = ObservedWebSocket.CLOSED
        this.dispatchEvent(new CloseEvent('close', { code: 1000, reason: 'client closed' }))
      }
      send() {}
    }

    Object.defineProperty(window, 'WebSocket', { configurable: true, value: ObservedWebSocket })
    Object.defineProperty(window, '__observedWebSocketUrls', { configurable: true, value: ObservedWebSocket.urls })
  })

  let setupRequired = true
  let welcomeCompleted = false
  let authenticated = false
  await page.route('**/auth/setup', async route => {
    if (route.request().resourceType() === 'document') {
      await route.continue()
      return
    }
    if (route.request().method() === 'POST') {
      setupRequired = false
      authenticated = true
    }
    await route.fulfill({ json: { setup_required: setupRequired, welcome_completed: welcomeCompleted } })
  })
  await page.route('**/auth/check', async route => {
    await route.fulfill({ json: { authenticated, user: authenticated ? { username: 'synthetic' } : null } })
  })
  await page.route('**/auth/initial-setup', async route => {
    setupRequired = false
    await route.fulfill({ json: { ok: true } })
  })
  await page.route('**/auth/onboarding/complete', async route => {
    welcomeCompleted = true
    await route.fulfill({ json: { ok: true } })
  })
  await page.route('**/auth/logout', async route => {
    authenticated = false
    await route.fulfill({ json: { ok: true } })
  })
  await page.route('**/api/recording/settings', async route => {
    await route.fulfill({ json: {
      enabled: true, output_directory: '/recordings', default_quality: 'best', use_chapters: true,
    } })
  })
  await page.route('**/api/**', async route => {
    await route.fulfill({ json: {} })
  })

  await page.goto('/auth/setup')
  await page.locator('#wiz-username').fill('synthetic-admin')
  await page.locator('#wiz-password').fill('synthetic-password')
  await page.locator('#wiz-confirm').fill('synthetic-password')
  await page.getByRole('button', { name: 'Create Admin & Continue' }).click()
  await page.getByRole('button', { name: 'Save & Continue' }).click()
  await page.getByRole('button', { name: 'Skip & Continue' }).click()
  await page.getByRole('button', { name: 'Go to Dashboard' }).click()

  await expect(page).toHaveURL(/\/$/)
  const expectedSocketCount = useMockData ? 0 : 1
  await expect.poll(() => page.evaluate(() => (window as unknown as { __observedWebSocketUrls: string[] }).__observedWebSocketUrls.length)).toBe(expectedSocketCount)
  if (!useMockData) {
    await expect(page.evaluate(() => (window as unknown as { __observedWebSocketUrls: string[] }).__observedWebSocketUrls[0])).resolves.toMatch(/\/ws$/)
  }

  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL(/\/auth\/login/)
  await expect.poll(() => page.evaluate(() => (window as unknown as { __observedWebSocketUrls: string[] }).__observedWebSocketUrls.length)).toBe(expectedSocketCount)
})
