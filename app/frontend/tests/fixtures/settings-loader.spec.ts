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
      '/api/streamers', '/api/favorites', '/api/keys', '/api/categories', '/api/categories/',
    ])
    const data: Record<string, unknown> = {
      '/api/settings': { notification_url: '', notifications_enabled: true },
      '/api/recording/settings': {
        enabled: true, output_directory: '/recordings', default_quality: 'best', use_chapters: true,
      },
      '/api/notifications/state': { notifications: [], unread_count: 0 },
      '/api/twitch/connection-status': { connected: false, valid: false, expires_at: null },
      '/api/version': { version: 'synthetic-settings-test' },
      '/api/recording/filename-presets': { presets: [] },
      '/api/proxy/list': {
        proxies: [],
        system_config: {
          enable_proxy: true, proxy_health_check_enabled: false,
          proxy_health_check_interval_seconds: 300,
          proxy_max_consecutive_failures: 3, fallback_to_direct_connection: true,
        },
      },
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

// A real pointer must hit the checkbox, not URL help painted above it.
test('notification URL editing leaves the checkbox reachable by mouse and touch', async ({ page, isMobile }, testInfo) => {
  const writes = await installSettingsApi(page)
  await page.goto('/settings?section=notifications')
  const input = page.getByLabel('Notification Service URL')
  const checkbox = page.getByRole('checkbox', { name: 'Enable Notifications', exact: true })
  for (const openHelp of [false, true]) {
    if (openHelp) {
      const help = page.locator('summary', { hasText: 'Notification URL help' })
      if (isMobile) await help.tap()
      else await help.click()
      await expect(page.getByRole('link', { name: 'Apprise Documentation' })).toBeVisible()
    }
    await input.fill(`https://synthetic.invalid/notifications?help=${openHelp}`)
    await checkbox.scrollIntoViewIfNeeded()
    const hit = await checkbox.evaluate(element => {
      const rect = element.getBoundingClientRect()
      const target = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
      return { reachable: target === element, target: target?.outerHTML }
    })
    await testInfo.attach(`checkbox-center-hit-help-${openHelp}`, { body: JSON.stringify(hit), contentType: 'application/json' })
    expect.soft(hit.reachable, JSON.stringify(hit)).toBe(true)
    if (isMobile) await checkbox.tap()
    else await checkbox.click()
    await expect(checkbox).toBeChecked({ checked: !openHelp })
  }
  expect(writes).toEqual([])
})

test('notification URL help supports keyboard disclosure, documentation and dismissal without a trap', async ({ page }) => {
  const writes = await installSettingsApi(page)
  await page.goto('/settings?section=notifications')
  const input = page.getByLabel('Notification Service URL')
  const help = page.locator('summary', { hasText: 'Notification URL help' })
  const link = page.getByRole('link', { name: 'Apprise Documentation' })
  const checkbox = page.getByRole('checkbox', { name: 'Enable Notifications', exact: true })
  await input.fill('invalid-url')
  await input.press('Tab')
  await expect(help).toBeFocused()
  await expect(input).toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByRole('button', { name: 'Save Settings', exact: true })).toBeDisabled()
  await help.press('Space')
  await expect(link).toBeVisible()
  await help.press('Tab')
  await expect(link).toBeFocused()
  await expect(link).toHaveAttribute('href', 'https://github.com/caronc/apprise/wiki#notification-services')
  await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  await page.context().route('https://github.com/caronc/apprise/wiki*', route => route.fulfill({
    contentType: 'text/html', body: '<title>Synthetic documentation navigation</title>',
  }))
  const popupPromise = page.waitForEvent('popup')
  await link.press('Enter')
  const popup = await popupPromise
  await expect(popup).toHaveURL('https://github.com/caronc/apprise/wiki#notification-services')
  await popup.close()
  await link.press('Escape')
  await expect(link).toBeHidden()
  await expect(help).toBeFocused()
  await help.press('Enter')
  await expect(link).toBeVisible()
  await help.press('Space')
  await expect(link).toBeHidden()
  await help.press('Tab')
  await expect(checkbox).toBeFocused()
  await checkbox.press('Space')
  await expect(checkbox).toBeChecked()
  await input.fill('https://synthetic.invalid/notifications')
  await input.press('Tab')
  await expect(input).not.toHaveAttribute('aria-invalid', 'true')
  await expect(page.getByRole('button', { name: 'Save Settings', exact: true })).toBeEnabled()
  expect(writes).toEqual([])
})

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

test('every settings option displays only its own panel in both navigation directions', async ({ page }, testInfo) => {
  const writes = await installSettingsApi(page)
  const pageErrors: string[] = []
  const directiveWarnings: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('console', message => {
    if (message.text().includes('Runtime directive used on component with non-element root node'))
      directiveWarnings.push(message.text())
  })
  const sections = [
    { id: 'notifications', name: /^Notifications /, marker: () => page.getByLabel('Notification Service URL') },
    { id: 'recording', name: /^Recording /, marker: () => page.getByRole('heading', { name: 'Basic Recording Settings', exact: true }) },
    { id: 'storage', name: /^Storage /, marker: () => page.getByRole('heading', { name: 'Storage & Cleanup Management', exact: true }) },
    { id: 'favorites', name: /^Favorite Games /, marker: () => page.getByPlaceholder('Search for game...') },
    { id: 'pwa', name: /^PWA & Mobile /, marker: () => page.getByRole('heading', { name: 'Progressive Web App', exact: true }) },
    { id: 'api-keys', name: /^API Keys /, marker: () => page.getByRole('button', { name: 'Create API Key', exact: true }) },
    { id: 'proxy', name: /^Proxy Management /, marker: () => page.getByRole('heading', { name: 'Proxy System Status', exact: true }) },
    { id: 'twitch', name: /^Twitch Connection /, marker: () => page.getByLabel('Twitch OAuth token') },
    { id: 'about', name: /^About /, marker: () => page.getByText('Automated stream recording and management system for Twitch content creators.', { exact: true }) },
  ]
  await page.goto('/settings?section=notifications')
  await expect(sections[0].marker()).toBeVisible()
  const options = await page.getByLabel('Choose settings section').locator('option').evaluateAll(elements =>
    elements.map(element => (element as HTMLOptionElement).value))
  expect(options.sort()).toEqual(sections.map(section => section.id).sort())
  const visited: string[] = []
  for (const selected of [...sections, ...sections.toReversed()]) {
    await switchSection(page, selected.id, selected.name)
    await expect(selected.marker()).toBeVisible()
    for (const other of sections) {
      if (other.id !== selected.id) await expect(other.marker(), `${other.id} hidden while ${selected.id} is selected`).toBeHidden()
    }
    visited.push(selected.id)
  }
  await testInfo.attach('visited-settings', { body: JSON.stringify(visited), contentType: 'application/json' })
  await page.screenshot({ path: testInfo.outputPath('settings-correct-panel.png') })
  expect(directiveWarnings).toEqual([])
  expect(pageErrors).toEqual([])
  expect(writes).toEqual([])
})

test('keeps an unsaved notification draft through About without saving it', async ({ page }) => {
  const writes = await installSettingsApi(page)
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto('/settings?section=notifications')
  const input = page.getByLabel('Notification Service URL')
  const draft = 'https://synthetic.invalid/unsaved-settings-draft'
  await input.fill(draft)
  for (let visit = 0; visit < 3; visit++) {
    await switchSection(page, 'about', /^About /)
    await expect(page.getByText('Automated stream recording and management system for Twitch content creators.', { exact: true })).toBeVisible()
    await expect(input).toBeHidden()
    await switchSection(page, 'recording', /^Recording /)
    await expect(page.getByRole('heading', { name: 'Basic Recording Settings', exact: true })).toBeVisible()
    await expect(input).toBeHidden()
    await switchSection(page, 'notifications', /^Notifications /)
    await expect(input).toHaveValue(draft)
  }
  expect(writes).toEqual([])
  expect(pageErrors).toEqual([])
})

test('opens About directly before lazily visiting a settings panel', async ({ page }) => {
  const writes = await installSettingsApi(page)
  const pageErrors: string[] = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto('/settings?section=about')
  await expect(page.getByText('Automated stream recording and management system for Twitch content creators.', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Notification Service URL')).toHaveCount(0)
  await switchSection(page, 'notifications', /^Notifications /)
  await expect(page.getByLabel('Notification Service URL')).toBeVisible()
  expect(writes).toEqual([])
  expect(pageErrors).toEqual([])
})
