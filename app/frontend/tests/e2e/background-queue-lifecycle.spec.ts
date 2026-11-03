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
