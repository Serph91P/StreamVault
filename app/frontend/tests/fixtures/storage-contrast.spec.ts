import { expect, test, type Locator } from '@playwright/test'
import axe from 'axe-core'

// Catches legacy highlight/white button pairs and static Sass label overrides
// using the real built styles, including translucent ancestor surfaces.
async function measure(target: Locator) {
  return target.evaluate(element => {
    const rgba = (value: string) => {
      const channels = value.match(/[\d.]+/g)!.map(Number)
      return [...channels.slice(0, 3), channels[3] ?? 1]
    }
    const over = (front: number[], back: number[]) => front.slice(0, 3).map((v, i) => v * front[3] + back[i] * (1 - front[3]))
    const luminance = (color: number[]) => color.map(v => {
      v /= 255
      return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4
    }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0)
    const chain: Element[] = []
    for (let node: Element | null = element; node; node = node.parentElement) chain.unshift(node)
    let background = [255, 255, 255]
    const ancestors = chain.map(node => {
      const style = getComputedStyle(node)
      background = over(rgba(style.backgroundColor), background)
      return { tag: node.tagName, classes: node.className, background: style.backgroundColor, image: style.backgroundImage, opacity: style.opacity }
    })
    const style = getComputedStyle(element)
    const foreground = over(rgba(style.color), background)
    const a = luminance(foreground), b = luminance(background)
    return {
      ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05),
      foreground, background, ancestors, fontSize: style.fontSize, fontWeight: style.fontWeight,
      active: element.matches(':active'), hover: element.matches(':hover'), focusVisible: element.matches(':focus-visible'),
    }
  })
}

async function settled(target: Locator) {
  await target.evaluate(async element => {
    await Promise.all(element.getAnimations().filter(animation => Number.isFinite(Number(animation.effect?.getComputedTiming().endTime))).map(animation => animation.finished))
  })
}

for (const theme of ['light', 'dark'] as const) {
  test(`Storage enabled contrast and native controls ${theme}`, async ({ page, isMobile }, info) => {
    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
    const writes: Array<{ path: string; body: Record<string, unknown> }> = []
    const external: string[] = []
    let settings = {
      enabled: true, default_quality: 'best', filename_preset: 'default', filename_template: '{streamer}/{title}',
      supported_codecs: 'h264,h265', use_chapters: true, max_streams_per_streamer: 7,
      cleanup_policy: { type: 'count', threshold: 10, preserve_favorites: true, preserve_categories: [] },
    }
    await page.routeWebSocket(/.*/, socket => socket.onMessage(message => {
      if (String(message).includes('ping')) socket.send(JSON.stringify({ type: 'pong' }))
    }))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      // The shipped MOCK channel has a remote avatar; fulfill that read locally.
      if (url.href === 'https://static-cdn.jtvnw.net/jtv_user_pictures/2b1f0b6e-8b0c-4f3a-8b1a-1f0b6e8b0c4f-profile_image-300x300.png' && request.method() === 'GET') {
        return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1" />' })
      }
      if (url.origin !== 'http://127.0.0.1:4183') { external.push(url.origin + url.pathname); return route.abort() }
      if (!/^\/(api|auth)\//.test(url.pathname)) return route.continue()
      if (request.method() !== 'GET') {
        writes.push({ path: url.pathname, body: request.postDataJSON() })
        if (url.pathname !== '/api/recording/settings' || request.method() !== 'POST') return route.fulfill({ status: 405, json: {} })
        settings = { ...settings, ...request.postDataJSON() }
      }
      const replies: Record<string, unknown> = {
        '/auth/setup': { setup_required: false, welcome_completed: true },
        '/auth/check': { authenticated: true, user: { username: 'synthetic-admin' } },
        '/api/settings': {}, '/api/recording/settings': settings,
        '/api/recording/streamers': [{ streamer_id: 1, username: 'synthetic-1', enabled: true, quality: '', use_global_cleanup_policy: true, cleanup_policy: null }],
        '/api/recording/active': [], '/api/settings/streamer': [],
        '/api/streamers/streamer/1': {
          id: 1, username: 'synthetic-1', name: 'Synthetic Channel', is_live: false,
          recording: { streamer_id: 1, username: 'synthetic-1', enabled: true, quality: '', use_global_cleanup_policy: true, cleanup_policy: null },
          notifications: { streamer_id: 1, username: 'synthetic-1', notify_online: true, notify_offline: true, notify_update: true, notify_favorite_category: true },
        },
        '/api/streamers/1/streams': { streams: [] },
        '/api/recording/storage/1': { totalSize: 1024, recordingCount: 1, oldestRecording: '2026-10-01', newestRecording: '2026-10-01' },
        '/api/recording/filename-presets': { presets: [] },
        '/api/categories': { categories: [{ id: 1, name: 'Games' }] },
        '/api/notifications/state': { notifications: [], unread_count: 0 }, '/api/version': { version: 'synthetic-storage-contrast' },
      }
      return route.fulfill({ json: replies[url.pathname] ?? [] })
    })
    await page.goto('/settings?section=storage')
    const editor = page.locator('.settings-content .cleanup-policy-editor')
    const save = editor.getByRole('button', { name: 'Save Cleanup Policy', exact: true })
    const input = editor.getByLabel('Number of recordings to keep:', { exact: true })
    const threshold = editor.locator('label').filter({ hasText: 'Number of recordings to keep:' })
    await expect(editor).toHaveCount(1)
    await expect(save).toBeEnabled()
    await expect(input).toHaveValue('10')
    await expect(editor.locator('select[multiple] option')).toHaveText(['Games'])
    await expect.poll(() => page.locator('html').getAttribute('data-theme')).toBe(theme === 'light' ? 'light' : null)
    await editor.evaluate(async () => {
      await Promise.all(document.getAnimations().filter(animation => Number.isFinite(Number(animation.effect?.getComputedTiming().endTime))).map(animation => animation.finished))
    })
    const measurements: Record<string, Awaited<ReturnType<typeof measure>>> = {}
    async function check(name: string, target: Locator) {
      await settled(target)
      const result = await measure(target)
      measurements[name] = result
      expect(result.ancestors.every(node => node.opacity === '1'), `${name}: no disabled/transient opacity`).toBe(true)
      expect(result.ancestors.every(node => node.image === 'none'), `${name}: no unmeasured gradient`).toBe(true)
      expect.soft(result.ratio, `${name}: normal-text AA`).toBeGreaterThanOrEqual(4.5)
    }
    await check('threshold', threshold)
    await check('idle', save)
    await save.hover()
    await check('hover', save)
    expect(measurements.hover.hover).toBe(true)
    await page.mouse.move(0, 0)
    await save.focus()
    await page.keyboard.press('Shift+Tab')
    await page.keyboard.press('Tab')
    await expect(save).toBeFocused()
    await check('keyboard-focus', save)
    expect(measurements['keyboard-focus'].focusVisible).toBe(true)
    if (isMobile) await save.tap({ trial: true })
    else await save.click({ trial: true })
    const box = (await save.boundingBox())!
    if (isMobile) {
      // A held touch does not expose :active in this Chromium emulation.
      // Hold native Space to measure enabled :active in the touch context.
      await save.focus()
      await page.keyboard.down('Space')
      await check('active', save)
      expect(measurements.active.active).toBe(true)
      await input.focus()
      await page.keyboard.up('Space')
    } else {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
      await page.mouse.down()
      await check('active', save)
      expect(measurements.active.active).toBe(true)
      await page.mouse.move(0, 0)
      await page.mouse.up()
    }
    await page.addScriptTag({ content: axe.source })
    const scan = await page.evaluate(async () => (window as unknown as { axe: typeof axe }).axe.run('.cleanup-policy-editor form', { runOnly: ['color-contrast'] }))
    await info.attach('contrast-states', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' })
    await info.attach('axe', { body: JSON.stringify(scan, null, 2), contentType: 'application/json' })
    expect.soft(scan.violations.map(issue => ({ id: issue.id, targets: issue.nodes.map(node => node.target) }))).toEqual([])
    // Gradient incompletes are retained in the attachment, never called passes.
    await threshold.click()
    await expect(input).toBeFocused()
    await input.fill('11')
    await input.press('ArrowUp')
    await expect(input).toHaveValue('12')
    await input.press('ArrowDown')
    await expect(input).toHaveValue('11')
    await editor.getByLabel('Cleanup Policy:', { exact: true }).selectOption('size')
    await expect(editor.getByLabel('Maximum storage size (GB):', { exact: true })).toHaveValue('11')
    await expect(save).toBeEnabled()
    expect(writes).toEqual([])
    if (isMobile) await save.tap()
    else {
      await save.focus()
      await page.keyboard.press('Enter')
    }
    await expect.poll(() => writes.length).toBe(1)
    await expect(editor.getByLabel('Maximum storage size (GB):', { exact: true })).toHaveValue('11')
    expect(writes).toEqual([{ path: '/api/recording/settings', body: expect.objectContaining({ max_streams_per_streamer: 7, cleanup_policy: { type: 'size', threshold: 11, preserve_favorites: true, preserve_categories: [] } }) }])
    await expect(save).toBeEnabled()
    expect(external).toEqual([])
    await info.attach('synthetic-save-transport', { body: JSON.stringify(writes), contentType: 'application/json' })

    // Same component outside the Settings selector, inside the channel dialog.
    await page.goto('/streamers/1?tab=settings')
    await page.getByRole('button', { name: 'Aufbewahrung', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Cleanup Policy for synthetic-1', exact: true })
    await expect(dialog.getByText('Storage Statistics', { exact: true })).toBeVisible()
    await dialog.getByLabel('Use Global Cleanup Policy').uncheck()
    const dialogInput = dialog.getByLabel('Number of recordings to keep:', { exact: true })
    await expect(dialogInput).toBeEnabled()
    const dialogLabel = dialog.locator('label').filter({ hasText: 'Number of recordings to keep:' })
    await dialog.evaluate(async element => {
      await Promise.all(element.getAnimations().filter(animation => Number.isFinite(Number(animation.effect?.getComputedTiming().endTime))).map(animation => animation.finished))
    })
    await check('dialog-threshold', dialogLabel)
    await dialogLabel.click()
    await expect(dialogInput).toBeFocused()
    await dialogInput.fill('12')
    await dialog.getByLabel('Cleanup Policy:', { exact: true }).selectOption('size')
    await expect(dialog.getByLabel('Maximum storage size (GB):', { exact: true })).toHaveValue('12')
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    expect(writes).toHaveLength(1)
    expect(external).toEqual([])
    await info.attach('dialog-label-contrast', { body: JSON.stringify(measurements['dialog-threshold'], null, 2), contentType: 'application/json' })
  })
}
