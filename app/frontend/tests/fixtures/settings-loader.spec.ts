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
  const mobileSelect = page.getByLabel('Einstellungsbereich wählen')
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
    await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
    await expect(page.locator('.panel-load-error')).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Benachrichtigungen – Einstellungen', exact: true })).toBeFocused()
    await switchSection(page, 'twitch', /^Twitch-Verbindung /)
    await expect(page.getByLabel('Twitch OAuth token')).toBeVisible()
    await switchSection(page, 'notifications', /^Benachrichtigungen /)
    await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
    await page.reload()
    await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
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
    { id: 'notifications', name: /^Benachrichtigungen /, marker: () => page.getByLabel('URL des Benachrichtigungsdienstes') },
    { id: 'recording', name: /^Aufnahme /, marker: () => page.getByRole('heading', { name: 'Globale Aufnahmevorgaben', exact: true }) },
    { id: 'storage', name: /^Speicher und Aufbewahrung /, marker: () => page.getByRole('heading', { name: 'Speicher und Aufbewahrung', level: 3, exact: true }) },
    { id: 'favorites', name: /^Lieblingsspiele /, marker: () => page.getByPlaceholder('Search for game...') },
    { id: 'pwa', name: /^App und Mobilgeräte /, marker: () => page.getByRole('heading', { name: 'Progressive Web App', exact: true }) },
    { id: 'api-keys', name: /^API-Schlüssel /, marker: () => page.getByRole('button', { name: 'Create API Key', exact: true }) },
    { id: 'proxy', name: /^Proxy-Verwaltung /, marker: () => page.getByRole('heading', { name: 'Proxy System Status', exact: true }) },
    { id: 'twitch', name: /^Twitch-Verbindung /, marker: () => page.getByLabel('Twitch OAuth token') },
    { id: 'about', name: /^Über StreamVault /, marker: () => page.getByText('Automatische Aufzeichnung und Verwaltung von Twitch-Streams.', { exact: true }) },
  ]
  await page.goto('/settings?section=notifications')
  await expect(sections[0].marker()).toBeVisible()
  const options = await page.getByLabel('Einstellungsbereich wählen').locator('option').evaluateAll(elements =>
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
  const input = page.getByLabel('URL des Benachrichtigungsdienstes')
  const draft = 'https://synthetic.invalid/unsaved-settings-draft'
  await input.fill(draft)
  for (let visit = 0; visit < 3; visit++) {
    await switchSection(page, 'about', /^Über StreamVault /)
    await expect(page.getByText('Automatische Aufzeichnung und Verwaltung von Twitch-Streams.', { exact: true })).toBeVisible()
    await expect(input).toBeHidden()
    await switchSection(page, 'recording', /^Aufnahme /)
    await expect(page.getByRole('heading', { name: 'Globale Aufnahmevorgaben', exact: true })).toBeVisible()
    await expect(input).toBeHidden()
    await switchSection(page, 'notifications', /^Benachrichtigungen /)
    await expect(input).toHaveValue(draft)
  }
  expect(writes).toEqual([])
  expect(pageErrors).toEqual([])
})

test('opens About directly before lazily visiting a settings panel', async ({ page }) => {
  const writes = await installSettingsApi(page)
  const pageErrors: string[] = []
  const hostRequests: string[] = []
  const mediaRequests: string[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (/\/SettingsPanelHost-[^/]+\.js$/.test(path)) hostRequests.push(path)
    if (/\/(hls[.-]|LivePlayerView-|VideoPlayerView-)/.test(path)) mediaRequests.push(path)
  })
  page.on('pageerror', error => pageErrors.push(error.message))
  // Preserve the existing route-level lazy boundary. SettingsView itself
  // preloads its host on mount, including About, to keep panel drafts alive.
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Meine Kanäle', exact: true })).toBeVisible()
  expect(hostRequests).toEqual([])
  expect(mediaRequests).toEqual([])
  await page.goto('/settings?section=about')
  await expect(page.getByText('Automatische Aufzeichnung und Verwaltung von Twitch-Streams.', { exact: true })).toBeVisible()
  await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toHaveCount(0)
  expect(mediaRequests).toEqual([])
  await switchSection(page, 'notifications', /^Benachrichtigungen /)
  await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
  expect(hostRequests.length).toBeGreaterThan(0)
  expect(mediaRequests).toEqual([])
  expect(writes).toEqual([])
  expect(pageErrors).toEqual([])
})

for (const section of ['recording', 'storage']) {
  test(`cold ${section} deep link loads the shared recording stylesheet`, async ({ page }) => {
    const writes = await installSettingsApi(page)
    await page.goto(`/settings?section=${section}`)
    const panel = page.locator('.panel-block:visible').first()
    await expect(panel).toBeVisible()
    await expect(panel).toHaveCSS('padding-top', '20px')
    await expect(panel.locator('.section-icon').first()).toHaveCSS('width', '24px')
    await expect(panel.locator('.section-icon').first()).toHaveCSS('height', '24px')
    expect(writes).toEqual([])
  })
}
