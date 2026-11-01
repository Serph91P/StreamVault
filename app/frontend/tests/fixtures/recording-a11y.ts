import { expect, test, type Page } from '@playwright/test'
import axe from 'axe-core'
import { FILENAME_PRESETS } from '../../src/types/recording'

// Real application, styles, store and transport; only auth/API data is synthetic.
async function recordingApi(page: Page) {
  let settings = {
    enabled: true, default_quality: 'best', filename_preset: 'default',
    filename_template: '{streamer}/{title}', use_chapters: true,
    use_category_as_chapter_title: false, supported_codecs: 'h264,h265', prefer_higher_quality: true,
  }
  const streamers = [7, 8].map(streamer_id => ({
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
    const data: Record<string, unknown> = {
      '/api/settings': {}, '/api/recording/settings': settings,
      '/api/recording/streamers': streamers, '/api/recording/active': [],
      '/api/recording/filename-presets': { status: 'success', data: FILENAME_PRESETS },
      '/api/categories': { categories: [{ id: 1, name: 'Games' }, { id: 2, name: 'Music' }] },
      '/api/notifications/state': { notifications: [], unread_count: 0 },
      '/api/version': { version: 'synthetic-a11y-test' },
    }
    return route.fulfill({ json: data[path] ?? [] })
  })
  return writes
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`Recording accessibility (${theme})`, () => {
    test.beforeEach(async ({ page }) => {
      await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
      await recordingApi(page)
      await page.goto('/settings?section=recording')
      await expect(page.getByText('channel-8', { exact: true })).toBeVisible()
      await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe(theme === 'light' ? 'light' : null)
    })

    test('names every field, activates native labels and preserves keyboard editing', async ({ page }) => {
      const panel = page.getByRole('region', { name: 'Recording settings', exact: true })
      const fields = [
        ['Default Quality:', 'combobox'], ['Filename Template:', 'combobox'],
        ['Custom Filename Template:', 'textbox'], ['Supported Codecs:', 'combobox'],
        ...[7, 8].flatMap(id => [
          [`Record channel-${id}`, 'checkbox'], [`Quality for channel-${id}`, 'combobox'],
          [`Custom Filename for channel-${id}`, 'textbox'],
        ]),
      ]
      for (const [name, role] of fields) {
        const control = panel.getByRole(role as 'combobox' | 'textbox' | 'checkbox', { name, exact: true })
        await expect(control).toHaveCount(1)
        await expect(control).toBeVisible()
        const id = await control.getAttribute('id')
        expect(id).toBeTruthy()
        await expect(page.locator(`[id="${id}"]`)).toHaveCount(1)
        const label = panel.locator(`label[for="${id}"]`)
        await label.click()
        await expect(control).toBeFocused()
        await page.keyboard.press('Tab')
        await expect(control).not.toBeFocused()
        await page.keyboard.press('Shift+Tab')
        await expect(control).toBeFocused()
      }
      const ids = await panel.locator('input[id], select[id]').evaluateAll(nodes => nodes.map(node => node.id))
      expect(new Set(ids).size).toBe(ids.length)
      for (const name of ['Enable Recording', 'Create Chapters From Stream Events', 'Use Category as Chapter Title']) {
        const checkbox = panel.getByRole('checkbox', { name, exact: true })
        const previous = await checkbox.isChecked()
        await checkbox.focus()
        await page.keyboard.press('Space')
        await expect(checkbox).toBeChecked({ checked: !previous })
      }
      const quality = panel.getByLabel('Default Quality:', { exact: true })
      await quality.focus()
      await page.keyboard.press('Home')
      await page.keyboard.press('ArrowDown')
      await page.keyboard.press('Enter')
      await expect(quality).not.toHaveValue('best')
      const filename = panel.getByLabel('Custom Filename Template:', { exact: true })
      await filename.fill('typed-')
      await page.keyboard.type('{title}')
      await expect(filename).toHaveValue('typed-{title}')
      await panel.getByRole('button', { name: 'game', exact: true }).click()
      await expect(filename).toBeFocused()
      await expect(filename).toHaveValue('typed-{title}game')
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
    })
  })
}

for (const theme of ['light', 'dark'] as const) {
  test(`streamer policy dialog exposes names and native editing (${theme})`, async ({ page }, testInfo) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    const writes = await recordingApi(page)
    await page.goto('/settings?section=recording')
    await expect(page.getByText('channel-8', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Policy', exact: true }).first().click()
    const dialog = page.getByRole('dialog', { name: 'Cleanup Policy for channel-7', exact: true })
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
      path: '/api/recording/streamers/7/cleanup-policy',
      body: { cleanup_policy: { type: 'age', threshold: 23, preserve_favorites: false, preserve_categories: ['Games', 'Music'] }, use_global_cleanup_policy: false },
    }])
  })
}

test('recording labelled values retain exact save transport and reload hydration', async ({ page }, testInfo) => {
  const writes = await recordingApi(page)
  await page.goto('/settings?section=recording')
  const panel = page.getByRole('region', { name: 'Recording settings', exact: true })
  await expect(page.getByText('channel-8', { exact: true })).toBeVisible()
  await panel.getByLabel('Default Quality:', { exact: true }).selectOption('720p')
  const mock = testInfo.project.name.startsWith('mock-')
  const preset = panel.getByLabel('Filename Template:', { exact: true })
  if (mock) {
    // The genuine mock API intentionally returns no presets (services/api.ts).
    await expect(preset.locator('option')).toHaveCount(0)
  } else {
    await preset.selectOption('plex')
    await expect(panel.getByLabel('Custom Filename Template:', { exact: true })).toHaveValue('{streamer}/Season {year}-{month}/{streamer} - S{year}{month}E{episode:02d} - {title}')
  }
  await panel.getByLabel('Custom Filename Template:', { exact: true }).fill('saved/{title}')
  await panel.getByLabel('Supported Codecs:', { exact: true }).selectOption('av1')
  await panel.getByRole('button', { name: 'Save Settings', exact: true }).click()
  await expect.poll(() => writes.filter(item => item.path === '/api/recording/settings')).toEqual([{
    path: '/api/recording/settings', body: {
      enabled: true, filename_template: 'saved/{title}', filename_preset: mock ? 'default' : 'plex',
      default_quality: '720p', use_chapters: true, use_category_as_chapter_title: false,
    },
  }])
  // The existing transport omits codec preferences; the component emit is tested separately.
  // This accessibility fix must not silently change that pre-existing API contract (#933).
  await panel.getByLabel('Quality for channel-7', { exact: true }).selectOption('480p')
  await expect(panel.getByLabel('Quality for channel-7', { exact: true })).toHaveValue('480p')
  const filename = panel.getByLabel('Custom Filename for channel-8', { exact: true })
  await filename.fill('channel/{title}')
  await filename.press('Tab')
  await expect(filename).toHaveValue('channel/{title}')
  // Channel edits are covered through their exact component emits, not claimed as DB persistence.
  await page.reload()
  await expect(panel.getByLabel('Default Quality:', { exact: true })).toHaveValue('720p')
  await expect(panel.getByLabel('Custom Filename Template:', { exact: true })).toHaveValue('saved/{title}')

})
