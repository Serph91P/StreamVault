import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { syntheticReply } from './issue828SyntheticApi'

const rows = ['sub-1', 'sub-2'].map((id, i) => ({
  id, type: 'stream.online', status: 'enabled', created_at: '2026-09-23T12:00:00Z',
  condition: { broadcaster_user_id: String(42 + i) },
}))

type Failure = 'http500' | 'network'

async function fixture(page: Page, failure: Failure, initialFailure: boolean, theme: string) {
  const state = { listCalls: 0, deleteCalls: 0, failList: initialFailure, failDelete: true, empty: false,
    requests: [] as Array<{ method: string; path: string; outcome: string }>, errors: [] as string[] }
  let releaseDelete: (() => void) | undefined
  page.on('pageerror', error => state.errors.push(error.message))
  await page.addInitScript(value => localStorage.setItem('streamvault-theme', value), theme)
  await page.routeWebSocket(/.*/, socket => socket.close({ code: 1000, reason: 'Synthetic subscription fixture' }))
  await page.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== 'http://127.0.0.1:4196') return route.abort('blockedbyclient')
    if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
    const method = request.method()
    const path = url.pathname
    const fail = async () => {
      state.requests.push({ method, path, outcome: failure })
      return failure === 'network' ? route.abort('failed') : route.fulfill({ status: 500, json: { detail: 'Synthetic subscription service unavailable' } })
    }
    if (method === 'GET' && path === '/api/streamers/subscriptions') {
      state.listCalls++
      if (state.failList) return fail()
      state.requests.push({ method, path, outcome: '200' })
      return route.fulfill({ json: { total: state.empty ? 0 : rows.length, subscriptions: state.empty ? [] : rows } })
    }
    if (method === 'DELETE' && path === '/api/streamers/subscriptions/sub-1') {
      state.deleteCalls++
      if (state.failDelete) {
        await new Promise<void>(resolve => { releaseDelete = resolve })
        return fail()
      }
      state.requests.push({ method, path, outcome: '200' })
      return route.fulfill({ json: { success: true, message: 'Synthetic subscription removed' } })
    }
    let reply
    if (method === 'GET' && path === '/auth/setup') reply = { status: 200, body: { setup_required: false, welcome_completed: true } }
    else if (method === 'GET' && path === '/auth/check') reply = { status: 200, body: { authenticated: true } }
    else if (method === 'GET' && path === '/api/streamers') reply = { status: 200, body: { streamers: [
      { id: 1, twitch_id: '42', username: 'synthetic-alpha' }, { id: 2, twitch_id: '43', username: 'synthetic-beta' },
    ] } }
    else reply = syntheticReply(path, method)
    state.requests.push({ method, path, outcome: String(reply.status) })
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  return { state, releaseDelete: () => { expect(releaseDelete).toBeDefined(); releaseDelete!() } }
}

async function evidence(page: Page, info: TestInfo, state: unknown) {
  await info.attach('http-dom-evidence', { contentType: 'application/json', body: Buffer.from(JSON.stringify({ state, text: await page.locator('main').innerText() }, null, 2)) })
  await info.attach('subscription-screen', { contentType: 'image/png', body: await page.screenshot({ fullPage: true }) })
}

for (const failure of ['http500', 'network'] as const) {
  test(`${failure}: initial failure, deliberate retry, stale refresh and validated empty`, async ({ page }, info) => {
    const { state } = await fixture(page, failure, true, info.project.name.includes('dark') ? 'dark' : 'light')
    await page.goto('/subscriptions')
    const alert = page.getByRole('alert').filter({ hasText: 'Unable to load subscriptions' })
    await expect(alert).toBeVisible()
    await expect(page.getByText('No Subscriptions Found', { exact: true })).toHaveCount(0)
    expect(state.listCalls).toBe(1)
    await evidence(page, info, state)
    state.failList = false
    await alert.getByRole('button', { name: 'Retry' }).click()
    await expect(page.locator('.table-row')).toHaveCount(2)
    expect(state.listCalls).toBe(2)
    await expect(alert).toHaveCount(0)
    state.failList = true
    await page.getByRole('button', { name: 'Refresh', exact: true }).click()
    await expect(alert).toBeVisible()
    await expect(page.getByText('synthetic-alpha', { exact: true })).toBeVisible()
    await expect(page.locator('.table-row')).toHaveCount(2)
    expect(state.listCalls).toBe(3)
    await evidence(page, info, state)
    state.failList = false
    state.empty = true
    await alert.getByRole('button', { name: 'Retry' }).click()
    await expect(page.getByText('No Subscriptions Found', { exact: true })).toBeVisible()
    await expect(alert).toHaveCount(0)
    expect(state.listCalls).toBe(4)
    expect(state.deleteCalls).toBe(0)
    expect(state.errors).toEqual([])
    await evidence(page, info, state)
  })

  test(`${failure}: single-delete failure is visible and preserves both rows`, async ({ page }, info) => {
    const harness = await fixture(page, failure, false, info.project.name.includes('dark') ? 'dark' : 'light')
    const { state } = harness
    page.on('dialog', dialog => dialog.accept())
    await page.goto('/subscriptions')
    await expect(page.locator('.table-row')).toHaveCount(2)
    const button = page.locator('.table-row').filter({ hasText: 'synthetic-alpha' }).getByRole('button', { name: 'Delete subscription' })
    if (info.project.use.hasTouch) await button.tap()
    else await button.click()
    await expect.poll(() => state.deleteCalls).toBe(1)
    harness.releaseDelete()
    const alert = page.getByRole('alert').filter({ hasText: 'Unable to delete subscription' })
    await expect(alert).toBeVisible()
    await expect(page.locator('.table-row')).toHaveCount(2)
    await expect(button).toBeEnabled()
    const target = await button.boundingBox()
    expect(target?.width).toBeGreaterThanOrEqual(44)
    expect(target?.height).toBeGreaterThanOrEqual(44)
    expect(state.deleteCalls).toBe(1)
    await evidence(page, info, state)
    state.failDelete = false
    if (info.project.use.hasTouch) await button.tap()
    else await button.click()
    await expect(page.locator('.table-row')).toHaveCount(1)
    await expect(page.getByText('synthetic-beta', { exact: true })).toBeVisible()
    await expect(alert).toHaveCount(0)
    expect(state.deleteCalls).toBe(2)
    expect(state.listCalls).toBe(1)
    expect(state.errors).toEqual([])
    await evidence(page, info, state)
  })
}

test('pending row blocks duplicate deletes and conflicting bulk actions', async ({ page }, info) => {
  const harness = await fixture(page, 'http500', false, info.project.name.includes('dark') ? 'dark' : 'light')
  page.on('dialog', dialog => dialog.accept())
  await page.goto('/subscriptions')
  await expect(page.locator('.table-row')).toHaveCount(2)
  const button = page.locator('.table-row').first().getByRole('button', { name: 'Delete subscription' })
  await button.click()
  await expect.poll(() => harness.state.deleteCalls).toBe(1)
  await expect(button).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Delete All', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Resubscribe All', exact: true })).toBeDisabled()
  await button.dispatchEvent('click')
  expect(harness.state.deleteCalls).toBe(1)
  harness.releaseDelete()
  await expect(page.getByRole('alert').filter({ hasText: 'Unable to delete subscription' })).toBeVisible()
  await expect(button).toBeEnabled()
  expect(harness.state.deleteCalls).toBe(1)
  await evidence(page, info, harness.state)
})
