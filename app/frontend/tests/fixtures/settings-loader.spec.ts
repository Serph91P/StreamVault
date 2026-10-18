import { expect, test, type Page } from '@playwright/test'

// Run against isolated MOCK and REAL production artifacts.
// REAL requests below are synthetic HTTP fixtures, not a live installation.
async function installSettingsApi(page: Page) {
  const writes: string[] = []
  await page.route('**/auth/setup', route => route.fulfill({
    json: { setup_required: false, welcome_completed: true },
  }))
  await page.route('**/auth/check', route => route.fulfill({
    json: { authenticated: true, user: { username: 'synthetic-admin' } },
  }))
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'GET') writes.push(path)
    const arrays = new Set([
      '/api/settings/streamer', '/api/recording/streamers', '/api/recording/active',
      '/api/streamers', '/api/favorites', '/api/keys',
    ])
    const data: Record<string, unknown> = {
      '/api/settings': { notification_url: '', notifications_enabled: true },
      '/api/recording/settings': {
        enabled: true, output_directory: '/recordings', default_quality: 'best', use_chapters: true,
      },
      '/api/notifications/state': { notifications: [], unread_count: 0 },
      '/api/twitch/connection-status': { connected: false, valid: false, expires_at: null },
      '/api/version': { version: 'synthetic-settings-test' },
    }
    return route.fulfill({ json: arrays.has(path) ? [] : data[path] ?? {} })
  })
  return writes
}

async function switchSection(page: Page, section: string, name: RegExp) {
  const mobileSelect = page.getByLabel('Choose settings section')
  if (await mobileSelect.isVisible()) await mobileSelect.selectOption(section)
  else await page.getByRole('button', { name }).click()
}

for (const scenario of ['fresh assets', 'a cached loader from the previous deployment', 'an unavailable loader'] as const) {
  test(`Settings load with ${scenario}`, async ({ page }) => {
    const writes = await installSettingsApi(page)
    const pageErrors: string[] = []
    page.on('pageerror', error => pageErrors.push(error.message))
    const staleRequests: string[] = []
    const loaderRequests: string[] = []
    await page.route(/\/assets\/settings-panel-host-loader\.js(?:\?.*)?$/, route => {
      const url = new URL(route.request().url())
      loaderRequests.push(url.href)
      if (scenario === 'an unavailable loader') return route.abort('internetdisconnected')
      // Model a browser/proxy cache entry under the old, unversioned asset URL.
      // Its referenced chunk disappeared when the next image was deployed.
      if (scenario === 'a cached loader from the previous deployment' && !url.search) return route.fulfill({
        contentType: 'application/javascript',
        body: "export const loadSettingsPanelHost = () => import('./SettingsPanelHost-previous-deploy.js')",
      })
      return route.continue()
    })
    await page.route('**/assets/SettingsPanelHost-previous-deploy.js*', route => {
      staleRequests.push(route.request().url())
      return route.fulfill({ status: 404, contentType: 'application/javascript', body: '' })
    })

    await page.goto('/settings?section=notifications')
    await expect(page.getByLabel('Notification Service URL')).toBeVisible()
    await expect(page.locator('.panel-load-error')).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Notifications settings' })).toBeFocused()
    await switchSection(page, 'twitch', /^Twitch Connection /)
    await expect(page.getByLabel('Twitch OAuth token')).toBeVisible()
    await switchSection(page, 'notifications', /^Notifications /)
    await expect(page.getByLabel('Notification Service URL')).toBeVisible()
    await page.reload()
    await expect(page.getByLabel('Notification Service URL')).toBeVisible()
    expect(loaderRequests.length).toBeGreaterThan(0)
    expect(staleRequests).toEqual([])
    expect(writes).toEqual([])
    expect(pageErrors).toEqual([])
  })
}
