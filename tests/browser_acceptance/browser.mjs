import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
import assert from 'node:assert/strict'
const { chromium, expect } = createRequire(process.env.FRONTEND_ROOT + '/package.json')('@playwright/test')
const origin = process.env.ACCEPTANCE_ORIGIN, output = process.env.ACCEPTANCE_OUTPUT
const browser = await chromium.launch({ executablePath: '/opt/data/agent/cache/ms-playwright/chromium-1243/chrome-linux64/chrome', headless: true })
const result = { scope: 'Final REAL candidate + production app factory/routers/services; disposable SQLite/media; zero API fulfills', cases: [] }
try {
  for (const device of [
    { name: 'desktop-light', width: 1440, height: 900, colorScheme: 'light', isMobile: false, hasTouch: false },
    { name: 'mobile-dark', width: 390, height: 844, colorScheme: 'dark', isMobile: true, hasTouch: true },
  ]) {
    const context = await browser.newContext({ viewport: { width: device.width, height: device.height }, colorScheme: device.colorScheme, isMobile: device.isMobile, hasTouch: device.hasTouch, serviceWorkers: 'block' })
    const page = await context.newPage(), frames = [], errors = [], responses = [], replays = []
    let documentLoads = 0, releaseQueue
    const connected = new Promise(resolve => { releaseQueue = resolve })
    await context.route('**/*', async route => {
      const url = new URL(route.request().url())
      if (url.origin !== origin) return route.abort()
      // Delay transport, never fulfill: hydrate the real initial snapshot AFTER connection.
      if (url.pathname.startsWith('/api/background-queue/')) await connected
      return route.continue()
    })
    page.on('domcontentloaded', () => documentLoads++)
    page.on('pageerror', error => errors.push(error.message))
    page.on('response', async response => {
      const path = new URL(response.url()).pathname
      if (path.startsWith('/api/')) responses.push({ path, status: response.status() })
      if (path === '/api/realtime/events' && response.ok()) {
        const data = await response.json()
        replays.push({ reset: data.reset, generation: data.generation, ids: data.events.map(event => event.data?.test_id).filter(Boolean) })
      }
    })
    page.on('websocket', ws => ws.on('framereceived', ({ payload }) => {
      try { const frame = JSON.parse(String(payload)); frames.push(frame); if (frame.type === 'connection.status') releaseQueue() } catch {}
    }))
    const api = (path, method = 'GET') => page.evaluate(async ({ path, method }) => {
      const response = await fetch(path, { method, credentials: 'include', headers: { Accept: 'application/json' } })
      return { status: response.status, body: await response.json() }
    }, { path, method })
    const state = async () => { const response = await api('/_acceptance/state'); assert.equal(response.status, 200); return response.body }
    const go = path => page.goto(origin + path)
    const button = name => page.getByRole('button', { name, exact: true })
    const shot = name => page.screenshot({ path: `${output}/${device.name}-${name}.png`, fullPage: true })
    try {
      await go('/auth/login?returnTo=%2F')
      await page.getByLabel('Username', { exact: true }).fill('realtime-admin')
      await page.getByLabel('Password', { exact: true }).fill(process.env.ACCEPTANCE_PASSWORD)
      const login = page.waitForResponse(response => response.url().endsWith('/auth/login') && response.request().method() === 'POST')
      await button('Sign In').click(); assert.equal((await login).status(), 200)
      await expect(page.getByRole('heading', { name: 'Meine Kanäle', exact: true })).toBeVisible()
      await expect(page.getByText('synthetic-channel', { exact: true }).first()).toBeVisible()
      await expect.poll(() => responses.some(response => response.path === '/api/background-queue/active-tasks' && response.status === 200)).toBe(true)
      assert.equal((await api('/_acceptance/seed', 'POST')).status, 200)

      await go('/settings?section=recording')
      await expect(page.getByRole('heading', { name: 'Globale Aufnahmevorgaben' })).toBeVisible()
      await expect(page.locator('.streamer-settings')).toHaveCount(0)
      const codecs = page.locator('.tab-panel select').last(), codec = device.isMobile ? 'av1' : 'h265'
      await codecs.selectOption(codec)
      const saved = page.waitForResponse(response => response.url().endsWith('/api/recording/settings') && response.request().method() === 'POST')
      await button('Einstellungen speichern').click(); assert.equal((await saved).status(), 200)
      assert.equal((await state()).global_codec, codec)
      await page.reload(); await expect(codecs).toHaveValue(codec)
      assert.equal((await api('/api/recording/settings')).body.supported_codecs, codec)
      await go('/settings?section=notifications')
      await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
      await expect(page.locator('.streamer-notifications')).toHaveCount(0)
      await go('/settings?section=twitch')
      await expect(page.getByLabel('Twitch OAuth token')).toBeVisible()
      await expect(page.locator('.tab-panel')).toHaveCount(0)

      await go('/streamers/manage')
      await expect(page.getByRole('heading', { name: 'Kanalverwaltung', exact: true })).toBeVisible()
      await button('Aufnahme für alle deaktivieren').click()
      await expect.poll(async () => (await state()).channel_enabled).toBe(false)
      await button('Für alle deaktivieren').click()
      await expect.poll(async () => (await state()).notify_online).toBe(false)
      await page.getByRole('link', { name: 'synthetic-channel', exact: true }).click()
      await expect(page.getByRole('checkbox', { name: /^Enable Recording/ })).not.toBeChecked()
      await page.getByRole('checkbox', { name: /^Enable Recording/ }).check()
      await page.locator('#field-recording-supported_codecs').selectOption('h264')
      const channelSave = page.waitForResponse(response => response.url().endsWith('/api/streamers/streamer/933/settings') && response.request().method() === 'PUT')
      await button('Save Settings').click(); assert.equal((await channelSave).status(), 200)
      assert.equal((await state()).channel_codec, 'h264'); assert.equal((await state()).global_codec, codec)
      await page.reload()
      await expect(page.locator('#field-recording-supported_codecs')).toHaveValue('h264')
      await expect(page.getByRole('checkbox', { name: /^Enable Recording/ })).toBeChecked()
      const initialUseGlobal = (await state()).use_global_cleanup_policy
      const policyLoaded = page.waitForResponse(response => new URL(response.url()).pathname === '/api/recording/streamers' && response.request().method() === 'GET')
      await button('Aufbewahrung').click()
      const cleanup = page.getByRole('dialog', { name: 'Cleanup Policy for synthetic-channel', exact: true })
      await policyLoaded
      await expect(cleanup.getByLabel('Use Global Cleanup Policy')).toBeChecked({ checked: initialUseGlobal })
      await expect(cleanup.getByText('Storage Statistics', { exact: true })).toBeVisible()
      await cleanup.getByLabel('Use Global Cleanup Policy').uncheck()
      await cleanup.locator('select').first().selectOption('count')
      await cleanup.locator('input[type="number"]').fill('3')
      await cleanup.getByRole('button', { name: 'Save Cleanup Policy', exact: true }).click()
      await expect(cleanup).toHaveCount(0)
      await expect.poll(async () => (await state()).use_global_cleanup_policy).toBe(false)
      assert.equal((await state()).cleanup_policy.threshold, 3)
      // Saving the other channel fields must not overwrite the independently owned policy.
      await button('Save Settings').click()
      await page.reload()
      await button('Aufbewahrung').click()
      await expect(cleanup.getByLabel('Use Global Cleanup Policy')).not.toBeChecked()
      await expect(cleanup.locator('input[type="number"]')).toHaveValue('3')
      await cleanup.getByRole('button', { name: 'Run Cleanup Now', exact: true }).click()
      const cleanupResult = page.getByRole('dialog', { name: 'Cleanup Results', exact: true })
      await expect(cleanupResult).toBeVisible()
      // Count 3 retains both synthetic recordings; actual service result/DB, not toast.
      assert.ok((await state()).streams.includes(933)); assert.ok((await state()).streams.includes(934))
      await cleanupResult.locator('footer').getByRole('button', { name: 'Close', exact: true }).click()
      await expect(cleanupResult).toHaveCount(0)
      await page.keyboard.press('Escape')
      await expect(cleanup).toHaveCount(0)
      await shot('channel-settings')

      await go('/activity?tab=history')
      const feed = page.locator('.activity-view .notification-feed')
      await expect(feed).toBeVisible()
      await expect.poll(() => frames.some(frame => frame.type === 'connection.status')).toBe(true)
      const before = { loads: documentLoads, origin: await page.evaluate(() => performance.timeOrigin) }
      const notification = await api('/api/settings/test-websocket-notification', 'POST')
      assert.equal(notification.status, 200)
      const id = notification.body.notification_id
      await expect.poll(() => frames.some(frame => frame.type === 'channel.update' && frame.data?.test_id === id)).toBe(true)
      const frame = frames.find(frame => frame.type === 'channel.update' && frame.data?.test_id === id)
      await expect(feed.locator('.notification-item').filter({ hasText: frame.data.message })).toHaveCount(1)
      await expect(feed.locator('.section-subtitle')).toContainText('1 unread')
      const replayCount = replays.length
      assert.equal((await api('/_acceptance/disconnect', 'POST')).status, 200)
      await expect.poll(() => replays.slice(replayCount).some(replay => replay.ids.includes('during-disconnect')), { timeout: 25000 }).toBe(true)
      await expect(feed.locator('.notification-item').filter({ hasText: 'Synthetic missed notification replay' })).toHaveCount(1)
      const generation = frames.filter(frame => frame.type === 'connection.status').at(-1).data.generation, pid = (await state()).pid, restartReplayCount = replays.length
      await page.getByRole('button', { name: /^Open background queue/ }).click()
      const cachedQueue = page.getByRole('dialog', { name: 'Background Queue', exact: true })
      await expect(cachedQueue.locator('.active-tasks-section')).toContainText('Synthetic acceptance')
      assert.equal((await api('/_acceptance/restart', 'POST')).status, 200)
      await expect(cachedQueue).toContainText('Live updates unavailable. Showing loaded queue data.')
      await expect(cachedQueue.locator('.active-tasks-section')).toContainText('Synthetic acceptance')
      await expect.poll(() => frames.some(frame => frame.type === 'connection.status' && frame.data.generation !== generation), { timeout: 40000 }).toBe(true)
      await expect.poll(() => replays.slice(restartReplayCount).some(replay => replay.reset && replay.ids.includes('after-process-restart')), { timeout: 15000 }).toBe(true)
      assert.notEqual((await state()).pid, pid)
      assert.equal((await state()).global_codec, codec)
      await button('Close background queue').click()
      await expect(feed.locator('.notification-item').filter({ hasText: 'Synthetic event after actual process restart' })).toHaveCount(1)
      const fresh = await api('/api/settings/test-websocket-notification', 'POST'), freshId = fresh.body.notification_id
      await expect.poll(() => frames.some(frame => frame.data?.test_id === freshId)).toBe(true)
      await expect(feed.locator('.notification-item').filter({ hasText: frames.find(frame => frame.data?.test_id === freshId).data.message })).toHaveCount(1)
      assert.equal(documentLoads, before.loads); assert.equal(await page.evaluate(() => performance.timeOrigin), before.origin)
      await shot('realtime')

      await page.getByRole('button', { name: /^Open background queue/ }).click()
      const queue = page.getByRole('dialog', { name: 'Background Queue', exact: true })
      await expect(queue.locator('.active-tasks-section')).toContainText('Synthetic acceptance')
      const queueReads = responses.filter(response => response.path.startsWith('/api/background-queue/')).length
      await api('/_acceptance/task/run', 'POST')
      await expect(queue.locator('.active-tasks-section .status-badge')).toHaveText('running')
      await api('/_acceptance/task/progress', 'POST'); await expect(queue.locator('.progress-text')).toHaveText('45%')
      await api('/_acceptance/task/complete', 'POST')
      await expect(queue.locator('.active-tasks-section')).toHaveCount(0)
      await expect(queue.locator('.recent-tasks-section')).toContainText('completed')
      await expect(queue.locator('.recent-tasks-section .task-item')).toHaveCount(1)
      await expect(queue.locator('.stat-item').filter({ hasText: 'Completed:' }).locator('.stat-value')).toHaveText('1')
      await expect(queue.locator('.stat-item').filter({ hasText: 'Pending:' }).locator('.stat-value')).toHaveText('0')
      assert.equal(responses.filter(response => response.path.startsWith('/api/background-queue/')).length, queueReads)
      await shot('queue'); await button('Close background queue').click()

      await go('/videos')
      await expect(page.getByText('Synthetic recording 933', { exact: true }).first()).toBeVisible()
      await page.getByRole('link', { name: 'Watch Synthetic recording 933', exact: true }).click()
      await expect(page).toHaveURL(/\/streamer\/933\/stream\/933\/watch/)
      const video = page.locator('video'); await expect(video).toBeVisible()
      await expect.poll(() => video.evaluate(element => element.readyState), { timeout: 15000 }).toBeGreaterThanOrEqual(2)
      if (await video.evaluate(element => element.paused)) await button('Play').click()
      await expect.poll(() => video.evaluate(element => element.currentTime)).toBeGreaterThan(0.1)
      await button('Pause').click()
      const seek = page.getByRole('slider', { name: 'Video progress', exact: true })
      await seek.press('Home'); await seek.press('ArrowRight')
      await expect.poll(() => video.evaluate(element => element.currentTime)).toBeGreaterThanOrEqual(5)
      await shot('player')
      await button('Delete').click(); await button('Delete Forever').click()
      await expect(page).toHaveURL(/\/videos$/)
      assert.ok(!(await state()).streams.includes(933))
      await go('/streamers/933?tab=videos')
      const remaining = page.locator('.stream-card').filter({ hasText: 'Synthetic recording 934' })
      await remaining.getByRole('button', { name: 'Expand stream details', exact: true }).click()
      await remaining.getByRole('button', { name: 'Delete Stream', exact: true }).click()
      const confirmation = page.getByRole('dialog', { name: 'Delete Stream', exact: true })
      await expect(confirmation).toBeVisible()
      assert.ok((await state()).streams.includes(934))
      await confirmation.getByRole('button', { name: 'Delete Stream', exact: true }).click()
      await expect.poll(async () => (await state()).streams.includes(934)).toBe(false)
      await expect(remaining).toHaveCount(0)
      await go('/overview')
      await expect(page.locator('.home-view')).toBeVisible()
      await go('/system')
      await expect(page.getByRole('heading', { name: 'System', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Settings', exact: true })).toBeVisible()
      assert.deepEqual(errors, []); assert.deepEqual(responses.filter(response => response.status >= 400), [])
      result.cases.push({ device: device.name, auth: 200, singleStreamDeleteSqlite: true, overviewAndSystemDirectLinks: true, globalCodecSaveSqliteReload: codec, channelOverrideSeparate: true, cleanupPolicySaveReloadAndRunRealService: true, cachedQueueVisibleDuringBackendOutage: true, managementPersistence: true, notificationResponseFrameDom: true, reconnectReplayDedupe: true, actualProcessRestart: true, generationResetReplayAndNewLiveEvent: true, realtimeDocumentReloads: 0, queueHydrationConnected: true, jobProgressCompletionWithoutRestRefresh: true, mediaDecodedPlayedSeeked: true, playerDeleteSqliteAndNavigation: true, pageErrors: errors, failedApiResponses: responses.filter(response => response.status >= 400) })
    } catch (error) {
      await shot('failure').catch(() => {})
      console.error(JSON.stringify({ device: device.name, location: page.url(), headings: await page.locator('h1,h2,h3').allTextContents(), frameTypes: frames.map(frame => frame.type), replays, errors, failedApiResponses: responses.filter(response => response.status >= 400), error: String(error) }))
      throw error
    } finally { await context.close() }
  }
  writeFileSync(output + '/result.json', JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2))
} finally { await browser.close() }
