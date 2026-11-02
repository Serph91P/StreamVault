import { expect, test, type Page, type TestInfo, type Locator } from '@playwright/test'
import axe from 'axe-core'
import { FILENAME_PRESETS } from '../../src/types/recording'

// Real application, styles, store and transport; only auth/API data is synthetic.
function channelIds(info: TestInfo) {
  return info.project.name.startsWith('mock-') ? [1, 2] : [7, 8]
}
async function recordingApi(page: Page) {
  let settings = {
    enabled: true, default_quality: 'best', filename_preset: 'default',
    filename_template: '{streamer}/{title}', use_chapters: true,
    use_category_as_chapter_title: false, supported_codecs: 'h264,h265', prefer_higher_quality: true,
  }
  const streamers = [1, 2, 7, 8].map(streamer_id => ({
    streamer_id, username: `channel-${streamer_id}`, enabled: true, quality: '', custom_filename: '',
  }))
  const writes: Array<{ path: string; body: unknown }> = []
  await page.route('**/auth/setup', route => route.fulfill({ json: { setup_required: false, welcome_completed: true } }))
  await page.route('**/auth/check', route => route.fulfill({ json: { authenticated: true, user: { username: 'synthetic-admin' } } }))
  await page.route('**/api/**', route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (request.method() !== 'GET') {
      const body = request.postDataJSON()
      writes.push({ path, body })
      if (path === '/api/recording/settings') settings = { ...settings, ...body }
      const streamer = streamers.find(item => path === `/api/recording/streamers/${item.streamer_id}`)
      if (streamer) Object.assign(streamer, body)
      return route.fulfill({ json: streamer ?? settings })
    }
    const channel = streamers.find(item => path === `/api/streamers/streamer/${item.streamer_id}`)
    const data: Record<string, unknown> = {
      '/api/settings': {}, '/api/recording/settings': settings,
      '/api/recording/streamers': streamers, '/api/recording/active': [],
      '/api/settings/streamer': [],
      '/api/recording/filename-presets': { status: 'success', data: FILENAME_PRESETS },
      '/api/categories': { categories: [{ id: 1, name: 'Games' }, { id: 2, name: 'Music' }] },
      '/api/notifications/state': { notifications: [], unread_count: 0 },
      '/api/version': { version: 'synthetic-a11y-test' },
    }
    if (channel) return route.fulfill({ json: {
      id: channel.streamer_id, username: channel.username, name: channel.username,
      is_live: false, is_recording: false, quality: 'best', profile_image_url: '',
      recording: { enabled: true, quality: '', custom_filename: '', supported_codecs: '' },
      notifications: {}, streams: [], total_streams: 0, total_duration: 0,
    } })
    return route.fulfill({ json: data[path] ?? [] })
  })
  return writes
}

async function openGlobal(page: Page) {
  await page.goto('/settings?section=recording')
  await expect(page.getByRole('heading', { name: 'Globale Aufnahmevorgaben', exact: true })).toBeVisible()
  return page.getByRole('region', { name: 'Aufnahme – Einstellungen', exact: true })
}
async function openChannel(page: Page, id: number) {
  await page.goto(`/streamers/${id}?tab=settings`)
  await expect(page.locator('.channel-settings-panel').getByRole('heading', { name: 'Aufnahme für diesen Kanal', exact: true })).toBeVisible()
  const fields = page.locator('.streamer-settings-fields')
  await expect(fields.getByRole('heading', { name: 'Recording Settings', exact: true })).toBeVisible()
  return fields
}
async function namedNativeTarget(page: Page, scope: Locator, name: string, role: 'combobox' | 'textbox') {
  const control = scope.getByRole(role, { name, exact: true })
  await expect(control).toHaveCount(1)
  await expect(control).toBeVisible()
  const id = await control.getAttribute('id')
  expect(id).toBeTruthy()
  await expect(page.locator(`[id="${id}"]`)).toHaveCount(1)
  await scope.locator(`label[for="${id}"]`).click()
  await expect(control).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(control).not.toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(control).toBeFocused()
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`Recording accessibility (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
      await recordingApi(page)
      await openGlobal(page)
      await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe(theme === 'light' ? 'light' : null)
    })

    test('names every field, activates native labels and preserves keyboard editing', async ({ page }, info) => {
      const panel = page.getByRole('region', { name: 'Aufnahme – Einstellungen', exact: true })
      for (const [name, role] of [
        ['Standardqualität:', 'combobox'], ['Dateinamenvorlage:', 'combobox'],
        ['Eigene Dateinamenvorlage:', 'textbox'], ['Erlaubte Codecs:', 'combobox'],
      ] as const) await namedNativeTarget(page, panel, name, role)
      const ids = await panel.locator('input[id], select[id]').evaluateAll(nodes => nodes.map(node => node.id))
      expect(new Set(ids).size).toBe(ids.length)
      for (const name of ['Automatische Aufnahme aktivieren', 'Kapitel aus Streamereignissen erzeugen', 'Kategorie als Kapiteltitel verwenden']) {
        const checkbox = panel.getByRole('checkbox', { name, exact: true })
        const previous = await checkbox.isChecked()
        await checkbox.focus()
        await page.keyboard.press('Space')
        await expect(checkbox).toBeChecked({ checked: !previous })
      }
      const quality = panel.getByLabel('Standardqualität:', { exact: true })
      await quality.focus()
      await page.keyboard.press('Home')
      await page.keyboard.press('ArrowDown')
      await page.keyboard.press('Enter')
      await expect(quality).not.toHaveValue('best')
      const filename = panel.getByLabel('Eigene Dateinamenvorlage:', { exact: true })
      await filename.fill('typed-')
      await page.keyboard.type('{title}')
      await expect(filename).toHaveValue('typed-{title}')
      await panel.getByRole('button', { name: 'game', exact: true }).click()
      await expect(filename).toBeFocused()
      await expect(filename).toHaveValue('typed-{title}game')
      for (const id of channelIds(info)) {
        const fields = await openChannel(page, id)
        for (const [name, role] of [
          ['Recording Quality:', 'combobox'], ['Custom Filename Template:', 'textbox'], ['Codec Preferences:', 'combobox'],
        ] as const) await namedNativeTarget(page, fields, name, role)
        const enabled = fields.getByRole('checkbox', { name: /^Enable Recording/ })
        const before = await enabled.isChecked()
        await enabled.focus()
        await page.keyboard.press('Space')
        await expect(enabled).toBeChecked({ checked: !before })
        await page.keyboard.press('Space')
        await expect(enabled).toBeChecked({ checked: before })
      }
    })

    test('help and example text meet AA in the rendered theme', async ({ page }, testInfo) => {
      await page.addScriptTag({ content: axe.source })
      const results = await page.evaluate(async () => window.axe.run('.settings-content', {
        runOnly: { type: 'rule', values: ['select-name', 'label', 'color-contrast'] },
      }))
      await testInfo.attach('recording-axe', { body: JSON.stringify(results, null, 2), contentType: 'application/json' })
      const contrast = results.violations.filter(item => item.id === 'color-contrast')
      expect(contrast, JSON.stringify(contrast.map(item => item.nodes), null, 2)).toEqual([])
      expect(results.violations).toEqual([])
      await openChannel(page, channelIds(testInfo)[0])
      await page.addScriptTag({ content: axe.source })
      const channel = await page.evaluate(async () => window.axe.run('.streamer-settings-fields', {
        runOnly: { type: 'rule', values: ['select-name', 'label', 'color-contrast'] },
      }))
      await testInfo.attach('channel-axe', { body: JSON.stringify(channel, null, 2), contentType: 'application/json' })
      expect(channel.violations).toEqual([])
    })
  })
}

for (const theme of ['light', 'dark'] as const) {
  test(`streamer policy dialog exposes names and native editing (${theme})`, async ({ page }, testInfo) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    const writes = await recordingApi(page)
    const id = channelIds(testInfo)[0]
    await openChannel(page, id)
    await page.locator('.channel-settings-panel').getByRole('button', { name: 'Aufbewahrung', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: `Cleanup Policy for channel-${id}`, exact: true })
    await expect(dialog).toBeVisible()
    const inherit = dialog.getByLabel('Use Global Cleanup Policy', { exact: true })
    await inherit.uncheck()
    await expect(dialog.getByRole('listbox')).toBeVisible()
    await page.addScriptTag({ content: axe.source })
    const results = await page.evaluate(async () => window.axe.run('.cleanup-policy-editor form', {
      runOnly: { type: 'rule', values: ['select-name', 'label', 'color-contrast'] },
    }))
    await testInfo.attach('policy-dialog-axe', { body: JSON.stringify(results, null, 2), contentType: 'application/json' })
    expect(results.violations).toEqual([])
    for (const name of ['Cleanup Policy:', 'Number of recordings to keep:', 'Preserve Categories:']) {
      const control = dialog.getByLabel(name, { exact: true })
      const id = await control.getAttribute('id')
      expect(id).toBeTruthy()
      await expect(page.locator(`[id="${id}"]`)).toHaveCount(1)
      await dialog.locator(`label[for="${id}"]`).click()
      await expect(control).toBeFocused()
      await page.keyboard.press('Tab')
      await page.keyboard.press('Shift+Tab')
      await expect(control).toBeFocused()
    }
    const type = dialog.getByRole('combobox', { name: 'Cleanup Policy:', exact: true })
    await type.focus()
    await page.keyboard.press('Home')
    await page.keyboard.press('ArrowDown')
    await page.keyboard.press('Enter')
    await expect(type).toHaveValue('size')
    const threshold = dialog.getByRole('spinbutton', { name: 'Maximum storage size (GB):', exact: true })
    await threshold.fill('23')
    await expect(threshold).toHaveValue('23')
    await type.selectOption('age')
    await expect(dialog.getByRole('spinbutton', { name: 'Maximum age (days):', exact: true })).toHaveValue('23')
    await dialog.getByRole('listbox', { name: 'Preserve Categories:', exact: true }).selectOption(['Games', 'Music'])
    await expect(dialog.getByRole('listbox')).toHaveValues(['Games', 'Music'])
    const favorites = dialog.getByRole('checkbox', { name: 'Preserve favorites', exact: true })
    await favorites.focus()
    await page.keyboard.press('Space')
    await expect(favorites).not.toBeChecked()
    await dialog.getByRole('button', { name: 'Save Cleanup Policy', exact: true }).click()
    await expect.poll(() => writes).toEqual([{
      path: `/api/recording/streamers/${id}/cleanup-policy`,
      body: { cleanup_policy: { type: 'age', threshold: 23, preserve_favorites: false, preserve_categories: ['Games', 'Music'] }, use_global_cleanup_policy: false },
    }])
  })
}

test('recording labelled values retain exact save transport and reload hydration', async ({ page }, testInfo) => {
  const writes = await recordingApi(page)
  const panel = await openGlobal(page)
  await panel.getByLabel('Standardqualität:', { exact: true }).selectOption('720p')
  const mock = testInfo.project.name.startsWith('mock-')
  const preset = panel.getByLabel('Dateinamenvorlage:', { exact: true })
  if (mock) {
    // The genuine mock API intentionally returns no presets (services/api.ts).
    await expect(preset.locator('option')).toHaveCount(0)
  } else {
    await preset.selectOption('plex')
    await expect(panel.getByLabel('Eigene Dateinamenvorlage:', { exact: true })).toHaveValue('{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}')
  }
  await panel.getByLabel('Eigene Dateinamenvorlage:', { exact: true }).fill('saved/{title}')
  await panel.getByLabel('Erlaubte Codecs:', { exact: true }).selectOption('av1')
  await panel.getByRole('button', { name: 'Einstellungen speichern', exact: true }).click()
  await expect.poll(() => writes.filter(item => item.path === '/api/recording/settings')).toEqual([{
    path: '/api/recording/settings', body: {
      enabled: true, filename_template: 'saved/{title}', filename_preset: mock ? 'default' : 'plex',
      default_quality: '720p', use_chapters: true, use_category_as_chapter_title: false,
      supported_codecs: 'av1',
    },
  }])
  const first = await openChannel(page, channelIds(testInfo)[0])
  await first.getByLabel('Recording Quality:', { exact: true }).selectOption('480p')
  await expect(first.getByLabel('Recording Quality:', { exact: true })).toHaveValue('480p')
  const second = await openChannel(page, channelIds(testInfo)[1])
  const filename = second.getByLabel('Custom Filename Template:', { exact: true })
  await filename.fill('channel/{title}')
  await filename.press('Tab')
  await expect(filename).toHaveValue('channel/{title}')
  // Channel edits are covered through their exact component emits, not claimed as DB persistence.
  await openGlobal(page)
  await page.reload()
  await expect(panel.getByLabel('Standardqualität:', { exact: true })).toHaveValue('720p')
  await expect(panel.getByLabel('Eigene Dateinamenvorlage:', { exact: true })).toHaveValue('saved/{title}')
  await expect(panel.getByLabel('Erlaubte Codecs:', { exact: true })).toHaveValue('av1')

})
