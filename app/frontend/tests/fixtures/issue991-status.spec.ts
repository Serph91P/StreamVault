import { expect, test, type WebSocketRoute } from '@playwright/test'

const paths = ['system', 'active-recordings', 'streamers', 'streams', 'notifications'].map(name => `/api/status/${name}`)

test('hydrates an already authenticated route after a full page load', async ({ page, request }) => {
  await request.post('/__fixture/reset')
  await request.post('/auth/login') // Synthetic cookie/session boundary, not a production login.
  await page.routeWebSocket('ws://127.0.0.1:4189/ws**', peer => peer.close({ code: 1012 }))
  await page.goto('/streamers')
  await expect(page.locator('.queue-status-indicator')).toBeVisible()
  await expect.poll(async () => {
    const entries = await (await request.get('/__fixture/requests')).json() as Array<{ path: string }>
    return paths.map(path => entries.filter(entry => entry.path === path).length)
  }).toEqual([1, 1, 1, 1, 1])
})

test('native browser offline/online reconnects the same status owner', async ({ page, request }) => {
  await request.post('/__fixture/reset')
  await request.post('/auth/login')
  let peers = 0
  let currentPeer: WebSocketRoute | undefined
  await page.routeWebSocket('ws://127.0.0.1:4189/ws**', peer => {
    peers++
    currentPeer = peer
    peer.onMessage(message => { if (String(message).includes('ping')) peer.send(JSON.stringify({ type: 'pong' })) })
  })
  await page.clock.install({ time: new Date('2026-11-01T12:00:00Z') })
  await page.clock.pauseAt(new Date('2026-11-01T12:00:00Z'))
  await page.goto('/streamers')
  await expect.poll(() => peers).toBe(1)
  await expect(page.locator('.queue-status-indicator')).toBeVisible()
  await expect(page.locator('.connectivity-banner')).toHaveCount(0)
  const counts = async () => {
    const entries = await (await request.get('/__fixture/requests')).json() as Array<{ path: string }>
    return paths.map(path => entries.filter(entry => entry.path === path).length)
  }
  await expect.poll(counts).toEqual([1, 1, 1, 1, 1])
  await page.context().setOffline(true)
  await expect(page.locator('.connectivity-banner')).toContainText('You are offline')
  // The synthetic peer must close too: Playwright's routed sockets survive context.setOffline.
  await currentPeer!.close({ code: 1012, reason: 'Synthetic transport loss during native offline' })
  await page.clock.runFor(60000)
  await expect.poll(counts).toEqual([1, 1, 1, 1, 1])
  await page.context().setOffline(false)
  await expect.poll(() => peers).toBe(2)
  await expect(page.locator('.connectivity-banner')).toHaveCount(0)
  await page.clock.runFor(1000)
  await expect.poll(counts).toEqual([2, 2, 2, 2, 2])
})

test('one shared hydration across routed consumers, reconnect/fallback and login lifecycle', async ({ page, request }, testInfo) => {
  await request.post('/__fixture/reset')
  const errors: string[] = []
  const unexpected: string[] = []
  const browserRequests: string[] = []
  const peers: WebSocketRoute[] = []
  let acceptSocket = true
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', req => { if (paths.includes(new URL(req.url()).pathname)) browserRequests.push(req.url()) })
  await page.route('**/*', route => {
    if (new URL(route.request().url()).origin !== 'http://127.0.0.1:4189') {
      unexpected.push(route.request().url())
      return route.abort('blockedbyclient')
    }
    return route.continue()
  })
  await page.routeWebSocket('ws://127.0.0.1:4189/ws**', peer => {
    peers.push(peer)
    if (!acceptSocket) return peer.close({ code: 1012, reason: 'Synthetic socket outage' })
    peer.onMessage(message => {
      if (String(message).includes('ping')) peer.send(JSON.stringify({ type: 'pong' }))
    })
  })
  const journal = async () => await (await request.get('/__fixture/requests')).json() as Array<{ method: string; path: string; query: string }>
  const statusCounts = async () => {
    const entries = await journal()
    return paths.map(path => entries.filter(entry => entry.path === path).length)
  }
  const expectBatches = async (number: number) => {
    await expect.poll(statusCounts).toEqual([number, number, number, number, number])
  }
  const login = async () => {
    await page.getByLabel('Username').fill('synthetic-test-user')
    await page.getByLabel('Password', { exact: true }).fill('synthetic-fixture-not-a-secret')
    await page.getByRole('button', { name: /Sign in|Log in|Login/i }).click()
    await expect(page.locator('.queue-status-indicator')).toBeVisible()
  }
  await page.clock.install({ time: new Date('2026-11-01T12:00:00Z') })
  await page.clock.pauseAt(new Date('2026-11-01T12:00:00Z'))
  await page.goto('/auth/login')
  await expect(page.locator('.login-view')).toBeVisible()
  await page.clock.runFor(180000)
  await expectBatches(0)
  expect(peers).toHaveLength(0)
  await login()
  await expectBatches(1)
  await expect.poll(() => peers.length).toBe(1)
  await page.clock.runFor(1000)
  await expectBatches(2) // Initial socket connection retains the existing delayed refresh.

  const recording = { id: 991, stream_id: 991, streamer_id: 1, streamer_name: 'synthetic_alpha', title: 'Synthetic recording', started_at: new Date().toISOString(), file_path: '/synthetic/991.mp4', status: 'recording', duration: 0 }
  peers.at(-1)!.send(JSON.stringify({ type: 'active_recordings_update', data: [recording] }))
  await expect(page.locator('.queue-count')).toHaveText('1')
  await page.locator('a[href="/videos"]').first().click()
  await expect(page).toHaveURL(/\/videos$/)
  await page.clock.runFor(1000)
  await expect(page.locator('.queue-count')).toHaveText('1')
  await expectBatches(2) // App + real BackgroundQueueMonitor use the same cache through navigation.

  await page.clock.runFor(180000)
  await expectBatches(2) // Connected socket never activates the emergency fallback.
  peers.at(-1)!.close({ code: 1012, reason: 'Synthetic reconnect' })
  await page.clock.runFor(5000)
  await expect.poll(() => peers.length).toBe(2)
  await expect(page.locator('.connectivity-banner')).toHaveCount(0)
  await page.clock.runFor(1000)
  await expectBatches(3)
  await expect(page.locator('.queue-count')).toHaveText('0') // Server snapshot wins on reconnect.

  acceptSocket = false
  peers.at(-1)!.close({ code: 1012, reason: 'Synthetic persistent socket outage' })
  await page.clock.runFor(120000)
  await expectBatches(3)
  await page.clock.runFor(60000)
  await expectBatches(4) // HTTP stays reachable; one owner makes one five-resource fallback.

  page.once('dialog', dialog => dialog.accept())
  await page.getByRole('button', { name: 'Logout', exact: true }).click()
  await expect(page.locator('.login-view')).toBeVisible()
  await page.clock.runFor(300000)
  await expectBatches(4)
  const socketsAtLogin = peers.length
  acceptSocket = true
  await login()
  await expectBatches(5)
  await expect.poll(() => peers.length).toBe(socketsAtLogin + 1)
  peers.at(-1)!.send(JSON.stringify({ type: 'active_recordings_update', data: [recording] }))
  await expect(page.locator('.queue-count')).toHaveText('1') // Wait for actual browser WS delivery before advancing its delayed refresh.
  await page.clock.runFor(1000)
  await expectBatches(6)
  await expect(page.locator('.queue-count')).toHaveText('0')
  const entries = await journal()
  expect(browserRequests).toHaveLength(30)
  expect(entries.filter(entry => entry.path.startsWith('/api/status/'))).toHaveLength(30)
  expect(entries.filter(entry => entry.method !== 'GET').map(entry => `${entry.method} ${entry.path}`)).toEqual(['POST /auth/login', 'POST /auth/keepalive', 'POST /auth/logout', 'POST /auth/keepalive', 'POST /auth/login'])
  expect(errors).toEqual([])
  expect(unexpected).toEqual([])
  await testInfo.attach('actual-local-http-request-journal', { body: JSON.stringify({ serverRequests: entries, browserStatusRequests: browserRequests, syntheticSocketCount: peers.length }, null, 2), contentType: 'application/json' })
  await page.screenshot({ path: testInfo.outputPath('shared-status-after-login.png') })
})
