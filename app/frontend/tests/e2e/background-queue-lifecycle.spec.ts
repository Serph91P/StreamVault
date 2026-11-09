import { expect, test, type Page } from '@playwright/test'
import { syntheticReply } from '../fixtures/issue828SyntheticApi'

const statusPath = '/api/admin/background-queue/status'
const status = {
  total_external_tasks: 2, total_active_tasks: 1, stuck_recordings: 1,
  continuous_orphaned: 0, unknown_tasks: 0, total_issues: 1,
  stuck_recording_tasks: ['synthetic-recording'], orphaned_recovery_tasks: [], unknown_task_names: [],
}

async function fixture(page: Page) {
  const requests: string[] = []
  const unknown: string[] = []
  const errors: string[] = []
  let statusCode = 200
  let holdStatus: Promise<void> | undefined
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/*', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (!/^\/(api|auth)\//.test(path) || request.isNavigationRequest()) return route.continue()
    requests.push(`${request.method()} ${path}`)
    if (path === statusPath) {
      await holdStatus
      return route.fulfill({ status: statusCode, json: statusCode === 200 ? status : { detail: 'synthetic failure' } })
    }
    if (path === '/api/admin/background-queue/cleanup/all' && request.method() === 'POST') {
      return route.fulfill({ json: { success: true, message: 'Synthetic cleanup completed', total_issues_fixed: 1 } })
    }
    if (path === '/api/admin/tests/quick-health' && request.method() === 'POST') {
      return route.fulfill({ json: { overall_status: 'healthy', checks: {} } })
    }
    if (path === '/api/admin/system/info') return route.fulfill({ json: { platform: 'synthetic', python_version: 'test', uptime: 0 } })
    if (path === '/api/admin/post-processing/stats') return route.fulfill({ json: { orphaned_recordings: 0, orphaned_segments: 0, total_size_gb: 0 } })
    const reply = syntheticReply(path, request.method())
    if (reply.status >= 400) unknown.push(`${request.method()} ${path}`)
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  await page.routeWebSocket(/.*/, socket => socket.close({ code: 1000, reason: 'Synthetic HTTP lifecycle fixture' }))
  await page.clock.install()
  await page.goto('/system')
  await expect(page.locator('.system-hub-card[href="/admin"]')).toBeVisible()
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 100))
  return {
    count: () => requests.filter(request => request === `GET ${statusPath}`).length,
    fail: (code: number) => { statusCode = code },
    hold: (promise: Promise<void>) => { holdStatus = promise },
    assertClean: () => { expect(unknown).toEqual([]); expect(errors).toEqual([]) },
  }
}
for (const width of [1440, 390]) {
  for (const theme of ['light', 'dark'] as const) {
    test.describe(`queue ${width}px ${theme}`, () => {
      test.use({ viewport: { width, height: 844 }, hasTouch: width === 390, isMobile: width === 390, colorScheme: theme })
  test('queue preview links to all loaded jobs and errors', async ({ page }, testInfo) => {
    // This regression seeds >3 jobs per group through the synthetic HTTP boundary,
    // which only exists on the REAL frontend. The shared MOCK project cannot seed
    // HTTP (its store reads mockData, not the network), so it runs only in the
    // dedicated real-build queue lifecycle config.
    test.skip(testInfo.project.metadata.useMockData === true, 'REAL-only: synthetic HTTP queue seed')
    const api = await fixture(page)
    const active = Array.from({ length: 5 }, (_, i) => ({
      id: `active-${i + 1}`, task_type: 'thumbnail', status: 'running', progress: 20,
      payload: { streamer_name: `ACTIVE-${i + 1}` },
    }))
    const recent = active.map((task, i) => ({
      ...task, id: `failed-${i + 1}`, status: 'failed',
      payload: { streamer_name: `FAILED-${i + 1}` }, error_message: `ERROR-${i + 1}`,
    }))
    await page.route('**/api/background-queue/active-tasks', route => route.fulfill({ json: active }))
    await page.route('**/api/background-queue/recent-tasks*', route => route.fulfill({ json: recent }))
    await page.clock.resume()
    await page.getByRole('button', { name: /Open background queue/ }).click()
    const preview = page.getByRole('dialog', { name: 'Background Queue' })
    await expect(preview.locator('.active-tasks-section .task-item')).toHaveCount(3)
    await expect(preview.locator('.recent-tasks-section .task-item')).toHaveCount(3)
    await preview.getByRole('link', { name: 'Vollständige Aktivität' }).click()
    await expect(page).toHaveURL(/\/activity$/)
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(page.locator('main .active-tasks-section .task-item')).toHaveCount(5)
    await expect(page.locator('main .recent-tasks-section .task-item')).toHaveCount(5)
    for (const i of [4, 5]) {
      await expect(page.locator('main').getByText(`ACTIVE-${i}`, { exact: true })).toBeVisible()
      await expect(page.locator('main').getByText(`FAILED-${i}`, { exact: true })).toBeVisible()
      await expect(page.locator('main').getByText(`ERROR-${i}`, { exact: true })).toBeVisible()
    }
    await page.reload()
    await expect(page.locator('main .task-item')).toHaveCount(10)
    await expect(page.locator('main')).toContainText('ERROR-5')
    await expect(page.locator('main')).toHaveCount(1)
    await expect(page.locator('h1')).toHaveCount(1)
    if (width === 390) {
      await page.setViewportSize({ width: 320, height: 844 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    }
    api.assertClean()
  })
    })
  }
}

async function enterAdmin(page: Page) {
  // Let the existing route transition finish before controlling polling time.
  await page.clock.resume()
  await page.locator('.system-hub-card[href="/admin"]').click()
  await expect(page.locator('.background-queue-admin')).toBeAttached()
  await page.locator('summary').filter({ hasText: 'Background Queue Tools' }).click()
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 100))
}
async function leaveAdmin(page: Page) {
  await page.clock.resume()
  await page.getByRole('link', { name: 'Back to System', exact: true }).click()
  await expect(page).toHaveURL(/\/system$/)
  await expect(page.locator('.background-queue-admin')).toHaveCount(0)
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 100))
}

test('admin navigation retains one active poller and no requests after leaving', async ({ page }) => {
  const api = await fixture(page)
  for (let visit = 1; visit <= 3; visit++) {
    await enterAdmin(page)
    await expect(page.locator('.background-queue-admin .status-item').first()).toContainText('External Tasks:2')
    expect(api.count()).toBe(visit * 2 - 1)
    await page.clock.runFor(30_000)
    await expect.poll(api.count).toBe(visit * 2)
    await expect(page.getByRole('button', { name: 'Refresh Status' })).toBeEnabled()
    await leaveAdmin(page)
    await page.clock.runFor(60_000)
    expect(api.count()).toBe(visit * 2)
  }
  api.assertClean()
})

test('leaving after cleanup cancels its delayed refresh', async ({ page }) => {
  const api = await fixture(page)
  await enterAdmin(page)
  await page.getByRole('button', { name: /Fix All Issues$/ }).click()
  await expect(page.locator('.background-queue-admin')).toContainText('Synthetic cleanup completed')
  await leaveAdmin(page)
  await page.clock.runFor(60_000)
  expect(api.count()).toBe(1)
  api.assertClean()
})

test('failed polling recovers and leaving aborts an in-flight status fetch', async ({ page }) => {
  const api = await fixture(page)
  api.fail(500)
  await enterAdmin(page)
  await expect(page.locator('.background-queue-admin')).toContainText('Error loading status')
  api.fail(200)
  await page.clock.runFor(30_000)
  await expect(page.locator('.background-queue-admin .status-item').first()).toContainText('External Tasks:2')
  let release!: () => void
  api.hold(new Promise<void>(resolve => { release = resolve }))
  await page.clock.runFor(30_000)
  await expect.poll(api.count).toBe(3)
  const aborted = page.waitForEvent('requestfailed', request => new URL(request.url()).pathname === statusPath)
  await leaveAdmin(page)
  await aborted
  release()
  await page.clock.runFor(60_000)
  expect(api.count()).toBe(3)
  api.assertClean()
})
