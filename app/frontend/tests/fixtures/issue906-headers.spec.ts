import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
import { readyForSettledMotion } from './issue828Browser'
import { syntheticReply } from './issue828SyntheticApi'

type Theme = 'dark' | 'light'

type RouteCase = {
  name: 'Settings' | 'Subscriptions' | 'Admin'
  path: '/settings' | '/subscriptions' | '/admin'
  title: RegExp
}

const viewports: Array<{ width: number; height: number; textScale?: number }> = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 863, height: 900 },
  { width: 1440, height: 900 },
  { width: 320, height: 900, textScale: 2 },
]

const routes: RouteCase[] = [
  { name: 'Settings', path: '/settings', title: /Einstellungen|Twitch-Verbindung/ },
  { name: 'Subscriptions', path: '/subscriptions', title: /Subscription Management/ },
  { name: 'Admin', path: '/admin', title: /Admin/ },
]

/**
 * Browser-bound synthetic HTTP fixture. It deliberately has no default success:
 * unknown routes return 501 and remain in the evidence log. The named routes
 * are the source contracts required to render the three real pages read-only.
 */
async function installIssue906SyntheticApi(page: Page, theme: Theme) {
  const origin = 'http://127.0.0.1:4187'
  const requests: Array<{ method: string; path: string; status: number }> = []
  const unknown: string[] = []
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))

  await page.addInitScript(({ selectedTheme }) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, { selectedTheme: theme })

  await page.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== origin) {
      unknown.push(`External ${url.origin}${url.pathname}`)
      return route.abort('blockedbyclient')
    }
    if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()

    const method = request.method()
    const reply = readonlyReply(url.pathname, method)
    requests.push({ method, path: url.pathname, status: reply.status })
    if (reply.status === 501) unknown.push(`${method} ${url.pathname}`)
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  await page.routeWebSocket(/.*/, socket => socket.close({ code: 1000, reason: 'Issue 906 synthetic REST-only fixture' }))
  return { requests, unknown, errors, origin, theme }
}

function readonlyReply(path: string, method: string): { status: number; body: unknown } {
  // AdminPanel automatically runs this diagnostic on mount. Intercept it here;
  // no real health checks or other POST operations are forwarded to a backend.
  if (method === 'POST' && path === '/api/admin/tests/quick-health') return {
    status: 200,
    body: { timestamp: '2026-01-01T00:00:00Z', overall_status: 'healthy', checks: { database: { status: 'healthy', message: 'Synthetic diagnostic only' } } },
  }
  if (method !== 'GET') return { status: 501, body: { detail: `Read-only Issue 906 fixture rejects ${method} ${path}` } }

  if (path === '/auth/setup') return { status: 200, body: { setup_required: false, welcome_completed: true } }
  if (path === '/auth/check') return { status: 200, body: { authenticated: true } }
  if (path === '/api/streamers/subscriptions') return { status: 200, body: { total: 0, subscriptions: [] } }
  if (path === '/api/streamers') return { status: 200, body: { streamers: [] } }
  if (path === '/api/settings') return { status: 200, body: { notification_url: '', notifications_enabled: false, apprise_docs_url: '', notify_online_global: false, notify_offline_global: false, notify_update_global: false } }
  if (path === '/api/settings/streamer') return { status: 200, body: [] }
  if (path === '/api/recording/settings') return { status: 200, body: { quality: 'best', format: 'mp4', auto_cleanup: false, retention_days: 30 } }
  if (path === '/api/recording/streamers' || path === '/api/recording/active') return { status: 200, body: [] }
  if (path === '/api/version') return { status: 200, body: { version: 'synthetic-test-only', frontend_version: 'synthetic-test-only' } }
  if (path === '/api/admin/system/info') return { status: 200, body: { platform: 'synthetic', python_version: 'synthetic', uptime: 0 } }
  if (path === '/api/admin/background-queue/status') return { status: 200, body: { total_external_tasks: 0, total_active_tasks: 0, stuck_recordings: 0, continuous_orphaned: 0, unknown_tasks: 0, total_issues: 0, stuck_recording_tasks: [], orphaned_recovery_tasks: [] } }
  if (path === '/api/admin/post-processing/stats') return { status: 200, body: { orphaned_recordings: 0, orphaned_segments: 0, total_size_gb: 0 } }
  if (path === '/api/twitch/connection-status') return { status: 200, body: { connected: false, valid: false, expires_at: null } }
  if (path === '/api/twitch/callback-url') return { status: 200, body: { url: 'http://127.0.0.1:4187/auth/callback' } }
  // Share the existing named status/queue contracts, including its strict 501 fallback.
  return syntheticReply(path, method)
}

async function assertUnifiedHeader(page: Page, route: RouteCase, captureHeader: () => Promise<unknown>) {
  // Support the current legacy header during RED; do not make the test pass
  // merely because a future PageHeader class is absent.
  const header = page.locator('.page-header, .view-header').filter({ has: page.getByRole('heading', { level: 1, name: route.title }) }).first()
  const title = header.getByRole('heading', { level: 1, name: route.title })
  const back = header.getByRole('link', { name: route.name === 'Settings' ? 'Zurück zum System' : 'Back to System', exact: true })

  await expect(header).toBeVisible()
  await expect(title).toBeVisible()
  await expect(back).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await readyForSettledMotion(header)

  const [headerBox, titleBox, backBox, iconBoxes] = await Promise.all([
    header.boundingBox(),
    title.boundingBox(),
    back.boundingBox(),
    header.locator('.page-header-title-group svg, .header-content svg').evaluateAll(nodes => nodes
      .filter(node => !node.closest('a'))
      .map(node => {
        const rect = node.getBoundingClientRect()
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
      })
      .filter(rect => rect.width > 0 && rect.height > 0)),
  ])
  expect(headerBox).not.toBeNull()
  expect(titleBox).not.toBeNull()
  expect(backBox).not.toBeNull()
  expect(iconBoxes.length).toBeGreaterThan(0)

  // Back is an independent row above the identity row. The visible page icon
  // belongs beside the H1, never beside the Back control.
  expect(backBox!.y + backBox!.height).toBeLessThanOrEqual(titleBox!.y + 0.5)
  expect(iconBoxes.some(icon => icon.y >= titleBox!.y - 0.5 && icon.y + icon.height <= titleBox!.y + titleBox!.height + 0.5)).toBe(true)

  const statusOrAction = route.name === 'Admin'
    ? header.getByText('Admin tools', { exact: true })
    : route.name === 'Subscriptions'
      ? header.getByRole('button', { name: 'Refresh', exact: true })
      : null
  if (statusOrAction) {
    await expect(statusOrAction).toBeVisible()
    const statusBox = await statusOrAction.boundingBox()
    expect(statusBox).not.toBeNull()
    if (page.viewportSize()!.width >= 1024) expect(statusBox!.x).toBeGreaterThanOrEqual(titleBox!.x)
    else expect(statusBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height - 0.5)
  }

  // Header anatomy must fit the viewport and the 44px Back control must have a
  // genuine hitpoint before its one real router navigation click.
  expect(backBox!.width).toBeGreaterThanOrEqual(43.9)
  expect(backBox!.height).toBeGreaterThanOrEqual(43.9)
  expect(backBox!.x).toBeGreaterThanOrEqual(0)
  expect(backBox!.y).toBeGreaterThanOrEqual(0)
  expect(backBox!.x + backBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(titleBox!.x).toBeGreaterThanOrEqual(0)
  expect(titleBox!.x + titleBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)

  await expect.poll(() => back.evaluate(element => {
    const rect = element.getBoundingClientRect()
    const point = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
    return element.contains(point)
  })).toBe(true)
  await back.click({ trial: true })
  await page.mouse.move(0, 0)
  await captureHeader()
  await back.click()
  await expect(page).toHaveURL(/\/system$/)
}

for (const viewport of viewports) {
  for (const theme of ['dark', 'light'] as const) {
    for (const route of routes) {
      test(`REAL synthetic ${route.name} header ${viewport.width}px ${theme}${viewport.textScale ? ' 200pct text' : ''}`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height })
        const api = await installIssue906SyntheticApi(page, theme)
        await page.goto(route.path, { waitUntil: 'domcontentloaded' })
        await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe(theme)
        if (viewport.textScale) await page.evaluate(scale => {
          const root = document.documentElement
          root.style.fontSize = `${parseFloat(getComputedStyle(root).fontSize) * scale}px`
        }, viewport.textScale)
        await assertUnifiedHeader(page, route, async () => {
          const stylePath = testInfo.outputPath('header-style.json')
          await writeFile(stylePath, JSON.stringify({ route: route.name, width: viewport.width, theme, scale: viewport.textScale || 1, back: await page.locator('.page-header-back-link').evaluate(element => {
              const svg = element.querySelector('svg')!
              return { color: getComputedStyle(element).color, iconColor: getComputedStyle(svg).color, stroke: getComputedStyle(svg).stroke, hovered: element.matches(':hover') }
            }) }))
          await testInfo.attach('header-style', {
            path: stylePath,
            contentType: 'application/json',
          })
          await page.screenshot({ path: testInfo.outputPath(`${route.name.toLowerCase()}-${viewport.width}-${theme}.png`) })
          if (route.name === 'Subscriptions') {
            const header = page.locator('.page-header')
            const count = () => api.requests.filter(request => request.path === '/api/streamers/subscriptions' || request.path === '/api/subscriptions').length
            const before = count()
            await header.getByRole('button', { name: 'Refresh', exact: true }).click()
            await expect.poll(count).toBeGreaterThan(before)
            await expect(header.getByRole('button', { name: 'Refresh', exact: true })).toBeEnabled()
            await expect(header.getByRole('button', { name: 'Delete All', exact: true })).toBeDisabled()
          }
        })

        // Origin and API provenance are asserted from the actual browser route
        // handler, rather than from mocked application state.
        expect(api.origin).toBe('http://127.0.0.1:4187')
        expect(api.requests.some(request => request.path === '/auth/setup')).toBe(true)
        expect(api.requests.some(request => request.path === '/auth/check')).toBe(true)
        expect(api.unknown).toEqual([])
        expect(api.requests.filter(request => request.method !== 'GET' && !(request.method === 'POST' && request.path === '/api/admin/tests/quick-health'))).toEqual([])
        expect(api.requests.filter(request => request.method === 'POST')).toHaveLength(route.name === 'Admin' ? 1 : 0)
        expect(api.errors).toEqual([])
      })
    }
  }
}
