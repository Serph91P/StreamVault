import { expect, test } from '@playwright/test'
import axe from 'axe-core'

for (const width of [320, 390, 1024, 1440]) {
  for (const theme of ['light', 'dark'] as const) {
    test(`global, channel, management and cleanup ${width} ${theme}`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ colorScheme: theme })
      await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
      const errors: string[] = []
      page.on('pageerror', error => errors.push(error.message))
      const writes: Array<{ path: string; body: Record<string, unknown> }> = []
      const policy = { type: 'count', threshold: 10, preserve_favorites: true, preserve_categories: [] }
      let globalRecording = { enabled: true, output_directory: '/synthetic/custom-recordings', default_quality: 'best', filename_template: '{streamer}', filename_preset: 'default', use_chapters: true, use_category_as_chapter_title: false, supported_codecs: 'h264', cleanup_policy: policy }
      const recording = [1, 2].map(id => ({ streamer_id: id, username: `synthetic-${id}`, enabled: true, quality: '', custom_filename: '', supported_codecs: '', use_global_cleanup_policy: true, cleanup_policy: null }))
      const notifications = [1, 2].map(id => ({ streamer_id: id, username: `synthetic-${id}`, notify_online: true, notify_offline: true, notify_update: true, notify_favorite_category: true }))
      let active = [{ id: 1, stream_id: 10, streamer_id: 1, streamer_name: 'synthetic-1', started_at: '2026-10-01T10:00:00Z', duration: 60, status: 'recording', file_path: '/synthetic/example.ts' }]
      let failSave = false
      let acceptOnly = false
      let releaseSave!: () => void
      const saveGate = new Promise<void>(resolve => { releaseSave = resolve })
      await page.routeWebSocket(/.*/, socket => socket.onMessage(message => {
        if (String(message).includes('ping')) socket.send(JSON.stringify({ type: 'pong' }))
      }))
      await page.route('**/*', async route => {
        const request = route.request()
        const url = new URL(request.url())
        if (url.origin !== 'http://127.0.0.1:4193') return route.abort('blockedbyclient')
        const path = url.pathname
        if (!/^\/(api|auth)\//.test(path)) return route.continue()
        const mutation = request.method() !== 'GET'
        const body = request.postData() ? request.postDataJSON() : {}
        if (mutation) writes.push({ path, body })
        if (path === '/auth/setup') return route.fulfill({ json: { setup_required: false, welcome_completed: true } })
        if (path === '/auth/check') return route.fulfill({ json: { authenticated: true, user: { username: 'synthetic-admin' } } })
        if (path === '/api/recording/settings') {
          if (mutation) await saveGate
          if (mutation && failSave) return route.fulfill({ status: 500, json: { detail: 'Synthetic save failure' } })
          if (mutation && acceptOnly) return route.fulfill({ status: 202, json: { ...globalRecording, ...body } })
          if (mutation) globalRecording = { ...globalRecording, ...body }
          return route.fulfill({ json: globalRecording })
        }
        if (path === '/api/recording/streamers') return route.fulfill({ json: recording })
        if (path === '/api/settings/streamer') return route.fulfill({ json: notifications })
        if (/^\/api\/recording\/streamers\/[12]$/.test(path)) {
          const channel = recording[Number(path.split('/').at(-1)) - 1]
          Object.assign(channel, body)
          return route.fulfill({ json: channel })
        }
        if (/^\/api\/settings\/streamer\/[12]$/.test(path)) {
          const channel = notifications[Number(path.split('/').at(-1)) - 1]
          Object.assign(channel, body)
          return route.fulfill({ json: channel })
        }
        if (path === '/api/recording/active') return route.fulfill({ json: active })
        if (path === '/api/recording/stop/1') { active = []; return route.fulfill({ json: { status: 'success' } }) }
        if (path === '/api/streamers/streamer/1/settings') {
          Object.assign(recording[0], body.recording)
          Object.assign(notifications[0], body.notifications)
          return route.fulfill({ json: { status: 'success' } })
        }
        if (path === '/api/streamers/streamer/1') return route.fulfill({ json: { id: 1, username: 'synthetic-1', name: 'Synthetic Channel', is_live: true, recording: recording[0], notifications: notifications[0] } })
        if (path === '/api/streamers/1/streams') return route.fulfill({ json: { streams: [] } })
        if (path === '/api/recording/streamers/1/cleanup-policy') { Object.assign(recording[0], body); return route.fulfill({ json: { status: 'success' } }) }
        if (path.startsWith('/api/recording/cleanup/1')) return route.fulfill({ json: { status: 'success', message: 'Synthetic cleanup completed', deleted_count: 0, deleted_paths: [] } })
        const replies: Record<string, unknown> = {
          '/api/settings': { notification_url: '', notifications_enabled: true, notify_online_global: true, notify_offline_global: true, notify_update_global: true },
          '/api/categories': { categories: [{ id: 1, name: 'Synthetic category' }] },
          '/api/recording/storage/1': { totalSize: 1024, recordingCount: 1, oldestRecording: '2026-10-01', newestRecording: '2026-10-01' },
          '/api/recording/filename-presets': { presets: [] },
          '/api/twitch/connection-status': { connected: false },
          '/api/version': { version: 'synthetic-settings-parity' },
          '/api/notifications/state': { last_read: null, last_cleared: null },
        }
        return route.fulfill({ json: replies[path] ?? {} })
      })

      await page.goto('/settings?section=recording')
      await expect(page.getByRole('heading', { name: 'Globale Aufnahmevorgaben' })).toBeVisible()
      await expect(page.locator('.streamer-settings')).toHaveCount(0)
      await expect(page.locator('.active-recordings')).toHaveCount(0)
      const codecs = page.locator('.tab-panel select').last()
      await codecs.selectOption('av1')
      await page.getByRole('button', { name: 'Einstellungen speichern', exact: true }).click()
      await expect(page.locator('.form-actions [data-state="pending"]')).toBeVisible()
      await expect(page.getByRole('button', { name: 'Wird gespeichert...', exact: true })).toBeDisabled()
      releaseSave()
      await expect.poll(() => globalRecording.supported_codecs).toBe('av1')
      await expect(page.locator('.form-actions [data-state="confirmed-success"]')).toBeVisible()
      expect(writes.find(write => write.path === '/api/recording/settings')?.body.output_directory).toBe('/synthetic/custom-recordings')
      await page.reload()
      await expect(codecs).toHaveValue('av1')
      acceptOnly = true
      await codecs.selectOption('h265')
      await page.getByRole('button', { name: 'Einstellungen speichern', exact: true }).click()
      await expect(page.locator('.form-actions [data-state="failure"]')).toBeVisible()
      await expect(page.locator('.form-actions [data-state="confirmed-success"]')).toHaveCount(0)
      expect(globalRecording.supported_codecs).toBe('av1')
      acceptOnly = false
      failSave = true
      await codecs.selectOption('h265')
      await page.getByRole('button', { name: 'Einstellungen speichern', exact: true }).click()
      await expect(page.getByText('Aufnahmeeinstellungen konnten nicht gespeichert werden', { exact: true })).toBeVisible()
      await expect(page.locator('.form-actions [data-state="failure"]')).toContainText('Entwurf bleibt erhalten')
      expect(globalRecording.supported_codecs).toBe('av1')
      failSave = false
      await page.goto('/settings?section=notifications')
      await expect(page.getByLabel('URL des Benachrichtigungsdienstes')).toBeVisible()
      await expect(page.locator('.streamer-notifications')).toHaveCount(0)
      await page.goto('/settings?section=twitch')
      await expect(page.getByLabel('Twitch OAuth token')).toBeVisible()
      await expect(page.locator('.tab-panel')).toHaveCount(0)

      await page.goto('/streamers/manage')
      await expect(page.getByRole('heading', { name: 'Kanalverwaltung', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'synthetic-1', exact: true })).toBeVisible()
      await page.getByRole('button', { name: 'Aufnahme für alle deaktivieren', exact: true }).click()
      await expect.poll(() => recording.every(channel => !channel.enabled)).toBe(true)
      await page.getByRole('button', { name: 'Für alle deaktivieren', exact: true }).click()
      await expect.poll(() => notifications.every(channel => !channel.notify_online && !channel.notify_offline && !channel.notify_update)).toBe(true)
      expect(notifications.every(channel => channel.notify_favorite_category)).toBe(true)
      await page.getByRole('button', { name: 'Aufnahme stoppen', exact: true }).click()
      await expect(page.locator('.active-recordings')).toHaveCount(0)
      await page.getByRole('link', { name: 'synthetic-1', exact: true }).click()
      await expect(page.getByRole('checkbox', { name: /^Enable Recording/ })).not.toBeChecked()
      await expect(page.locator('.channel-settings-panel tbody input')).toHaveCount(0)
      await expect(page.locator('.channel-settings-panel tbody select')).toHaveCount(0)
      await page.getByRole('checkbox', { name: /^Enable Recording/ }).check()
      await page.locator('#field-recording-supported_codecs').selectOption('av1')
      await page.getByRole('button', { name: 'Save Settings', exact: true }).click()
      await expect.poll(() => recording[0].supported_codecs).toBe('av1')
      await page.getByRole('button', { name: 'Alle an', exact: true }).click()
      await expect.poll(() => notifications[0].notify_online).toBe(true)
      await expect(page.getByRole('checkbox', { name: /^Online / })).toBeChecked()
      await page.getByRole('button', { name: 'Aufbewahrung', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: 'Cleanup Policy for synthetic-1', exact: true })
      await expect(dialog.getByText('Storage Statistics', { exact: true })).toBeVisible()
      await dialog.getByLabel('Use Global Cleanup Policy').uncheck()
      await dialog.locator('input[type="number"]').fill('3')
      await dialog.getByRole('button', { name: 'Save Cleanup Policy', exact: true }).click()
      await expect(dialog).toHaveCount(0)
      expect(recording[0].use_global_cleanup_policy).toBe(false)
      await page.getByRole('button', { name: 'Save Settings', exact: true }).click()
      await expect.poll(() => writes.filter(write => write.path === '/api/streamers/streamer/1/settings').length).toBe(2)
      expect(recording[0].use_global_cleanup_policy).toBe(false)
      await page.getByRole('button', { name: 'Aufbewahrung', exact: true }).click()
      await expect(dialog.getByLabel('Use Global Cleanup Policy')).not.toBeChecked()
      await dialog.getByRole('button', { name: 'Run Cleanup Now', exact: true }).click()
      await expect(page.getByText('Synthetic cleanup completed', { exact: true })).toBeVisible()
      await page.getByRole('dialog', { name: 'Cleanup Results', exact: true }).locator('footer').getByRole('button', { name: 'Close', exact: true }).click()
      await dialog.getByRole('button', { name: 'Apply Unsaved Policy (Deletes Recordings)', exact: true }).click()
      await expect(page.getByText('Synthetic cleanup completed', { exact: true })).toBeVisible()
      expect(writes.some(write => write.path === '/api/recording/cleanup/1/custom')).toBe(true)
      await page.getByRole('dialog', { name: 'Cleanup Results', exact: true }).locator('footer').getByRole('button', { name: 'Close', exact: true }).click()
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
      // Scan the stable page, not a transient half-opacity toast exit frame.
      await expect(page.locator('.toast')).toHaveCount(0)
      await page.addScriptTag({ content: axe.source })
      const violations = await page.evaluate(async () => (await (window as unknown as { axe: typeof axe }).axe.run(document, { runOnly: ['color-contrast'] })).violations)
      expect(violations.map(issue => ({ id: issue.id, nodes: issue.nodes.map(node => node.target) }))).toEqual([])
      const actionsOverlapDescription = await page.locator('.settings-actions').evaluate(element =>
        element.getBoundingClientRect().bottom > element.nextElementSibling!.getBoundingClientRect().top)
      expect(actionsOverlapDescription).toBe(false)
      await page.getByRole('button', { name: 'Alle an', exact: true }).click({ trial: true })
      await page.evaluate(() => window.scrollTo(0, 0))
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))))
      await page.screenshot({ path: testInfo.outputPath(`settings-viewport-${width}-${theme}.png`) })
      await page.screenshot({ path: testInfo.outputPath(`settings-parity-${width}-${theme}.png`), fullPage: true })
      await testInfo.attach('settings-mutations', { body: JSON.stringify(writes, null, 2), contentType: 'application/json' })
      expect(errors).toEqual([])
    })
  }
}
