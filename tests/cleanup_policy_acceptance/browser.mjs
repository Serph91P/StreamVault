import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
import assert from 'node:assert/strict'
const { chromium, expect } = createRequire(process.env.FRONTEND_ROOT + '/package.json')('@playwright/test')
const origin = process.env.ACCEPTANCE_ORIGIN
const output = process.env.ACCEPTANCE_OUTPUT
const browser = await chromium.launch({ headless: true })
const result = { scope: 'REAL build, actual product factory/routers/services, disposable SQLite; only failed POST seams', cases: [] }
try {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, serviceWorkers: 'block' })
    const page = await context.newPage()
    const errors = [], writes = []
    let seam = null
    page.on('pageerror', error => errors.push(error.message))
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin !== origin) return route.abort()
      assert.ok(!url.pathname.startsWith('/api/recording/cleanup/'), 'cleanup/deletion must never be invoked')
      if (request.method() === 'POST' && (url.pathname === '/api/recording/settings' || url.pathname.endsWith('/cleanup-policy'))) {
        writes.push({ path: url.pathname, body: request.postDataJSON() })
        if (seam === 'http500') return route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"synthetic write failure"}' })
        if (seam === 'network') return route.abort('failed')
      }
      return route.continue()
    })
    const go = path => page.goto(origin + path)
    const state = async () => {
      const response = await context.request.get(origin + '/_acceptance/state')
      assert.equal(response.status(), 200)
      return response.json()
    }
    const storeState = () => page.evaluate(() => {
      const store = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia._s.get('recordings')
      return JSON.parse(JSON.stringify({ global: store.settings?.cleanup_policy, channels: store.streamerSettings }))
    })
    await go('/auth/login?returnTo=%2F')
    await page.getByLabel('Username', { exact: true }).fill('policy-admin')
    await page.getByLabel('Password', { exact: true }).fill(process.env.ACCEPTANCE_PASSWORD)
    const login = page.waitForResponse(response => response.url().endsWith('/auth/login') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Sign In', exact: true }).click()
    assert.equal((await login).status(), 200)
    for (const target of ['global', 'channel', 'inherit']) {
      for (const failure of ['http500', 'network']) {
        await go('/settings?section=' + (target === 'global' ? 'storage' : 'recording'))
        let editor
        const openChannel = async () => {
          const legacy = page.locator('button[title="Configure cleanup policy for this streamer"]')
          // #933 moves the same production editor into the channel detail.
          await expect(page.locator('.settings-context-note').or(legacy)).toBeVisible()
          const channelFirst = await page.locator('.settings-context-note').count() > 0
          if (channelFirst) {
            await go('/streamers/947?tab=settings')
            await page.getByRole('button', { name: 'Aufbewahrung', exact: true }).click()
          } else await legacy.click()
          return page.getByRole('dialog', { name: 'Cleanup Policy for synthetic-policy', exact: true }).locator('.cleanup-policy-editor')
        }
        if (target === 'global') editor = page.locator('.cleanup-policy-editor')
        else editor = await openChannel()
        await expect(editor.getByRole('button', { name: 'Save Cleanup Policy', exact: true })).toBeVisible()
        // Wait for actual initialization before entering the draft.
        const loaded = await state()
        const initialPolicy = target === 'global' ? loaded.global : (loaded.inherits ? loaded.global : loaded.channel ?? loaded.global)
        if (initialPolicy) {
          await expect(editor.locator('input[type="number"]')).toHaveValue(String(initialPolicy.threshold))
          await expect(editor.locator('select').first()).toHaveValue(initialPolicy.type)
        }
        if (target !== 'global') {
          await expect.poll(async () => (await storeState()).channels.length).toBe(1)
          await expect(editor.getByLabel('Use Global Cleanup Policy')).toBeChecked({ checked: (await state()).inherits })
          await editor.getByLabel('Use Global Cleanup Policy').setChecked(target === 'inherit')
          if (target === 'inherit') await expect(editor.locator('input[type="number"]')).toHaveValue(String(loaded.global?.threshold ?? 10))
        }
        const threshold = target === 'inherit' ? Number(await editor.locator('input[type="number"]').inputValue()) : 40 + result.cases.length
        if (target !== 'inherit') {
          await editor.locator('select').first().selectOption('age')
          await editor.locator('input[type="number"]').fill(String(threshold))
          await editor.getByLabel('Preserve favorites', { exact: true }).uncheck()
        }
        const before = await state(), beforeStore = await storeState(), startWrites = writes.length
        seam = failure
        await editor.getByRole('button', { name: 'Save Cleanup Policy', exact: true }).click()
        await expect(editor.locator('.message.error')).toBeVisible()
        await expect(editor.locator('.message.success')).toHaveCount(0)
        await expect(editor.locator('input[type="number"]')).toHaveValue(String(threshold))
        await expect(editor.getByRole('button', { name: 'Save Cleanup Policy', exact: true })).toBeEnabled()
        assert.deepEqual(await state(), before)
        assert.deepEqual(await storeState(), beforeStore)
        assert.equal(writes.length, startWrites + 1)
        await page.screenshot({ path: `${output}/${viewport.width}-${target}-${failure}.png`, fullPage: true })
        seam = null
        await editor.getByRole('button', { name: 'Save Cleanup Policy', exact: true }).click()
        if (target === 'global') await expect(editor.locator('.message.success')).toBeVisible()
        else await expect(editor).toHaveCount(0)
        assert.equal(writes.length, startWrites + 2, 'one retry, no redundant parent write')
        assert.deepEqual(writes.at(-1), writes.at(-2), 'unchanged retry payload')
        const after = await state()
        if (target === 'inherit') {
          assert.equal(after.inherits, true)
          assert.equal(after.channel, null)
        } else {
          assert.deepEqual(after[target], { type: 'age', threshold, preserve_favorites: false, preserve_categories: [], preserve_timeframe: null })
          if (target === 'channel') assert.equal(after.inherits, false)
        }
        await page.reload()
        if (target !== 'global') {
          // Current page is already the correct settings/channel context.
          await page.locator('button[title="Configure cleanup policy for this streamer"]').or(page.getByRole('button', { name: 'Aufbewahrung', exact: true })).click()
          editor = page.getByRole('dialog', { name: 'Cleanup Policy for synthetic-policy', exact: true }).locator('.cleanup-policy-editor')
        }
        if (target === 'inherit') await expect(editor.getByLabel('Use Global Cleanup Policy')).toBeChecked()
        else {
          await expect(editor.locator('input[type="number"]')).toHaveValue(String(threshold))
          await expect(editor.locator('select').first()).toHaveValue('age')
          await expect(editor.getByLabel('Preserve favorites', { exact: true })).not.toBeChecked()
        }
        assert.deepEqual(await state(), after)
        result.cases.push({ viewport, target, failure, retainedDraft: true, unchangedDatabaseAndStoreOnFailure: true, retryIdentical: true, persistedAndReloaded: after })
      }
    }
    assert.deepEqual(errors, [])
    await context.close()
  }
  writeFileSync(output + '/result.json', JSON.stringify(result, null, 2))
  console.log(`PASS ${result.cases.length} real backend Save -> Failure -> Retry -> Reload journeys; zero cleanup/deletes`)
} finally {
  await browser.close()
}
