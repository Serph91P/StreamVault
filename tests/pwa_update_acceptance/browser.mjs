import { chromium, expect } from '../../app/frontend/node_modules/@playwright/test/index.mjs'
import { readFile, writeFile, symlink, rename } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'

const origin = process.env.PWA_TEST_ORIGIN
const output = process.env.PWA_TEST_OUTPUT
const expectLoss = process.env.PWA_EXPECT_LOSS === '1'
const full = process.env.PWA_FULL === '1'
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
async function selectBuild(dist) {
  const target = path.join(process.env.PWA_TEST_FRONTEND, 'dist')
  await symlink(dist, target + '.next')
  await rename(target + '.next', target)
  if (process.env.PWA_BACKEND_SWITCH) {
    const request = `${Date.now()}-${dist === process.env.PWA_TEST_OLD ? 'old' : 'new'}`
    await writeFile(process.env.PWA_BACKEND_SWITCH, request)
    await expect.poll(async () => {
      try { return await readFile(process.env.PWA_BACKEND_SWITCH + '.ready', 'utf8') }
      catch { return '' }
    }).toBe(request)
  }
}
async function verifyFactory(context, dist) {
  const compiled = await readFile(path.join(dist, 'sw.js'), 'utf8')
  const entries = [...compiled.matchAll(/\{url:"([^"]+)",revision:(?:"[^"]+"|null)\}/g)].map(m => m[1])
  expect(entries.length).toBeGreaterThan(0)
  expect(new Set(entries).size).toBe(entries.length)
  const inventory = []
  for (const entry of entries) {
    const response = await context.request.get(origin + '/' + entry, { maxRedirects: 0 })
    const bytes = await response.body()
    const relative = entry.startsWith('pwa/') ? entry.slice(4) : entry
    const expected = await readFile(path.join(dist, relative))
    inventory.push({ url: entry, status: response.status(), correctBytes: bytes.equals(expected), sha256: hash(bytes) })
    expect(response.status(), entry).toBe(200)
    expect(bytes.equals(expected), entry).toBe(true)
  }
  for (const icon of ['maskable-icon-512x512.png', 'maskable-icon-192x192.png', 'icon-512x512.png']) expect(entries).toContain(icon)
  const api = await context.request.get(origin + '/api/system/info', { headers: { Accept: 'application/json' }, maxRedirects: 0 })
  expect(api.status()).toBe(401)
  const privacy = []
  for (const [method, endpoint, status] of [
    ['GET', '/auth/login', 200], ['HEAD', '/auth/login', 200],
    ['GET', '/auth/private', 401], ['POST', '/api/system/info', 401],
  ]) {
    const response = await context.request.fetch(origin + endpoint, { method, headers: { Accept: 'application/json' }, maxRedirects: 0 })
    expect(response.status()).toBe(status)
    expect(response.headers()['content-type']).toContain('application/json')
    expect(response.headers()['cache-control']).toBeUndefined()
    privacy.push({ method, endpoint, status })
  }
  const htmlHead = await context.request.head(origin + '/auth/login', { headers: { Accept: 'text/html' } })
  expect(htmlHead.headers()['cache-control']).toBe('no-store')
  const servedWorker = await (await context.request.get(origin + '/sw.js')).text()
  expect(servedWorker).toContain(compiled)
  expect(servedWorker).toContain("importScripts('/pwa/push-sw.js')")
  const push = await (await context.request.get(origin + '/pwa/push-sw.js')).body()
  expect(push.equals(await readFile(new URL('../../app/frontend/public/push-sw.js', import.meta.url)))).toBe(true)
  return { inventory, privacy, protectedApi: api.status(), canonicalPushHash: hash(push), servedWorkerHash: hash(servedWorker) }
}

async function completeUpgrade(context, page, row, input, documents, requests, traffic, responses) {
  const selectSection = async (id, label) => {
    if (row.mobile) await page.getByLabel('Einstellungsbereich wählen', { exact: true }).selectOption(id)
    else await page.getByRole('button', { name: label, exact: true }).click()
  }
  row.factory = await verifyFactory(context, process.env.PWA_TEST_NEW)
  const username = page.getByLabel('Username', { exact: true })
  const password = page.getByLabel('Password', { exact: true })
  const signIn = page.getByRole('button', { name: 'Sign In', exact: true })
  await password.fill('synthetic-invalid-password')
  await signIn.click()
  await expect(page.getByRole('alert')).toBeVisible()
  expect(await input.evaluate(n => n.isConnected)).toBe(true)
  await expect(username).toHaveValue('synthetic-unsaved-pwa-name')
  expect(documents.length).toBe(row.baseline.documents)
  expect(responses.some(r => r.path === '/auth/login' && r.status === 401)).toBe(true)

  await page.route('**/auth/login', route => route.abort('failed'), { times: 1 })
  await signIn.click()
  await expect(page.getByRole('alert')).toContainText(/Connection|Network|failed|error/i)
  expect(await input.evaluate(n => n.isConnected)).toBe(true)
  expect(documents.length).toBe(row.baseline.documents)
  row.failedLoginPreserved = true

  const peer = await context.newPage()
  let peerDocuments = 0
  peer.on('domcontentloaded', () => peerDocuments++)
  await peer.goto(origin + '/auth/login?returnTo=%2Fsettings%3Fsection%3Dpwa%23install')
  await expect(peer.getByLabel('Username', { exact: true })).toBeVisible()
  await peer.waitForTimeout(500)
  await peer.getByLabel('Username', { exact: true }).fill('synthetic-pwa-admin')
  await peer.getByLabel('Password', { exact: true }).fill(process.env.PWA_TEST_PASSWORD)
  const peerBaseline = peerDocuments
  let releaseLogin
  const loginGate = new Promise(resolve => { releaseLogin = resolve })
  let heldLogin = false
  await peer.route('**/auth/login', async route => {
    if (route.request().method() === 'POST') { heldLogin = true; await loginGate }
    return route.continue()
  })
  await peer.getByRole('button', { name: 'Sign In', exact: true }).click()
  await expect.poll(() => heldLogin).toBe(true)
  expect(peerDocuments).toBe(peerBaseline)
  expect(await input.evaluate(n => n.isConnected)).toBe(true)
  releaseLogin()
  await expect(peer).toHaveURL(origin + '/settings?section=pwa#install')
  await expect(peer.getByRole('heading', { name: 'Progressive Web App', exact: true })).toBeVisible()
  await expect.poll(() => peerDocuments).toBe(peerBaseline + 1)
  await page.waitForTimeout(700)
  expect(documents.length).toBe(row.baseline.documents)
  expect(requests.length).toBe(row.baseline.requests)
  expect(await input.evaluate(n => n.isConnected)).toBe(true)
  await expect(username).toHaveValue('synthetic-unsaved-pwa-name')
  row.foreignActivationPreserved = true

  await username.fill('synthetic-pwa-admin')
  await password.fill(process.env.PWA_TEST_PASSWORD)
  const trafficStart = traffic.length
  await signIn.click()
  await expect(page).toHaveURL(origin + '/settings?section=pwa#install')
  await expect(page.getByRole('heading', { name: 'Progressive Web App', exact: true })).toBeVisible()
  await expect.poll(() => documents.length).toBe(row.baseline.documents + 1)
  expect(requests.length).toBe(row.baseline.requests + 1)
  const recoveryTraffic = traffic.slice(trafficStart)
  const recoveryDocument = recoveryTraffic.findIndex(r => r.type === 'document')
  expect(recoveryDocument).toBeGreaterThanOrEqual(0)
  expect(recoveryTraffic.slice(0, recoveryDocument).filter(r => r.type === 'script')).toEqual([])
  row.loginRecovery = { recoveryTraffic, documents: documents.length, requests: requests.length, target: page.url() }

  // Discover the next real build while the PWA panel is unmounted.
  await selectSection('about', 'Über StreamVault')
  await expect(page.getByRole('heading', { name: 'Progressive Web App', exact: true })).toHaveCount(0)
  await selectBuild(process.env.PWA_TEST_OLD)
  await page.evaluate(async () => { await (await navigator.serviceWorker.getRegistration()).update() })
  await expect.poll(() => page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)).toBe(true)
  await selectSection('pwa', 'App und Mobilgeräte')
  await expect(page.getByRole('button', { name: 'Update now', exact: true })).toBeVisible()
  await selectSection('about', 'Über StreamVault')
  await selectSection('pwa', 'App und Mobilgeräte')
  await expect(page.getByRole('button', { name: 'Update now', exact: true })).toBeVisible()
  const beforeExplicit = documents.length
  await page.getByRole('button', { name: 'Update now', exact: true }).click()
  await expect.poll(() => documents.length).toBe(beforeExplicit + 1)
  await expect(page.getByRole('heading', { name: 'Progressive Web App', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Update now', exact: true })).toHaveCount(0)
  row.explicitUpdateAfterRemount = { before: beforeExplicit, after: documents.length }
  await peer.close()

  // Discover a real new worker while a real login POST is already in flight.
  expect((await context.request.post(origin + '/auth/logout')).status()).toBe(200)
  await page.goto(origin + '/auth/login?returnTo=%2Fsettings%3Fsection%3Dpwa%23install')
  await expect(username).toBeVisible()
  await username.fill('synthetic-pwa-admin')
  await password.fill(process.env.PWA_TEST_PASSWORD)
  const inFlightInput = await username.elementHandle()
  const beforeInFlight = documents.length
  let releaseInFlight
  const inFlightGate = new Promise(resolve => { releaseInFlight = resolve })
  let inFlight = false
  await page.route('**/auth/login', async route => {
    if (route.request().method() === 'POST') { inFlight = true; await inFlightGate }
    await route.continue()
  })
  await signIn.click()
  await expect.poll(() => inFlight).toBe(true)
  await selectBuild(process.env.PWA_TEST_NEW)
  await page.evaluate(async () => { await (await navigator.serviceWorker.getRegistration()).update() })
  await expect.poll(() => page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()).waiting)).toBe(true)
  expect(documents.length).toBe(beforeInFlight)
  expect(await inFlightInput.evaluate(node => node.isConnected)).toBe(true)
  releaseInFlight()
  await expect(page).toHaveURL(origin + '/settings?section=pwa#install')
  await expect(page.getByRole('heading', { name: 'Progressive Web App', exact: true })).toBeVisible()
  await expect.poll(() => documents.length).toBe(beforeInFlight + 1)
  await page.unroute('**/auth/login')
  row.discoveryDuringLogin = { before: beforeInFlight, after: documents.length, target: page.url() }

  const persistent = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }))
  expect(JSON.stringify(persistent)).not.toContain('synthetic-unsaved-pwa-name')
  expect(JSON.stringify(persistent)).not.toContain(process.env.PWA_TEST_PASSWORD)
  row.noDraftInWebStorage = true
  const csrf = await context.request.post(origin + '/auth/logout', { headers: { Origin: 'https://untrusted.invalid', 'Sec-Fetch-Site': 'cross-site' } })
  expect(csrf.status()).toBe(403)
  row.csrfDenied = csrf.status()
  const cachedPaths = await page.evaluate(async () => {
    const paths = []
    for (const name of await caches.keys()) for (const request of await (await caches.open(name)).keys()) paths.push(new URL(request.url).pathname)
    return paths
  })
  expect(cachedPaths.filter(path => /^\/(auth|api)\//.test(path))).toEqual([])
  row.noPrivateCacheEntries = true
  await context.setOffline(true)
  await page.goto(origin + '/streamers?offline=pwa')
  await expect(page.locator('#app')).not.toBeEmpty()
  const offlineResponse = await page.evaluate(async () => {
    const response = await fetch('/pwa/push-sw.js')
    return { status: response.status, bytes: await response.text() }
  })
  expect(offlineResponse.status).toBe(200)
  expect(offlineResponse.bytes).toBe(await readFile(new URL('../../app/frontend/public/push-sw.js', import.meta.url), 'utf8'))
  row.offline = { shell: true, canonicalPush: true, navigation: page.url() }
  const offlineAuth = await context.newPage()
  await expect(offlineAuth.goto(origin + '/auth/login')).rejects.toThrow()
  await offlineAuth.close()
  row.offline.authDocumentNotCached = true
  await context.setOffline(false)
}

const browser = await chromium.launch({ headless: true,
  executablePath: process.env.PWA_CHROMIUM || '/opt/hermes/tools/chromium-1208/chrome-linux64/chrome',
  args: ['--no-sandbox'],
})
const results = []
try {
  for (const mobile of [false, true]) {
    await selectBuild(process.env.PWA_TEST_OLD)
    const context = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 }, isMobile: mobile, hasTouch: mobile })
    const page = await context.newPage()
    const documents = [], requests = [], submissions = [], workers = [], traffic = []
    const responses = []
    let releaseRequests
    let heldRequests = 0
    const requestGate = new Promise(resolve => { releaseRequests = resolve })
    if (full) await page.route('**/api/**', async route => {
      heldRequests++
      await requestGate
      await route.continue()
    })
    page.on('response', r => { if (/\/(api|auth)\//.test(new URL(r.url()).pathname)) responses.push({ path: new URL(r.url()).pathname, status: r.status() }) })
    page.on('domcontentloaded', () => documents.push(page.url()))
    page.on('request', r => {
      traffic.push({ path: new URL(r.url()).pathname, type: r.resourceType() })
      if (r.isNavigationRequest() && r.frame() === page.mainFrame()) requests.push(r.url())
      if (new URL(r.url()).pathname === '/auth/login' && r.method() === 'POST') submissions.push('POST')
    })
    const cdp = await context.newCDPSession(page)
    await cdp.send('ServiceWorker.enable')
    cdp.on('ServiceWorker.workerVersionUpdated', ({ versions }) => {
      for (const v of versions) workers.push({ versionId: v.versionId, status: v.status, scriptURL: v.scriptURL })
    })
    await page.goto(origin + '/auth/login?returnTo=%2Fsettings%3Fsection%3Dpwa%23install')
    const username = page.getByLabel('Username', { exact: true })
    await expect(username).toBeVisible()
    const coldInput = await username.elementHandle()
    await username.fill('synthetic-cold-draft')
    await page.evaluate(async () => { await navigator.serviceWorker.ready })
    await page.waitForTimeout(500)
    const cold = { documents: documents.length, requests: requests.length, connected: await coldInput.evaluate(n => n.isConnected), value: await username.inputValue() }
    expect(cold).toEqual({ documents: 1, requests: 1, connected: true, value: 'synthetic-cold-draft' })
    if (full) {
      await expect.poll(() => heldRequests).toBeGreaterThan(1)
      releaseRequests()
      // Native startup reads omit Accept: JSON: the original middleware redirects
      // them (307), rather than synthesizing a 401 in this factory acceptance.
      await expect.poll(() => responses.filter(r => r.status === 307 && r.path.startsWith('/api/')).length).toBe(heldRequests)
      expect(await coldInput.evaluate(n => n.isConnected)).toBe(true)
      await expect(username).toHaveValue('synthetic-cold-draft')
      expect(documents.length).toBe(1)
      await page.unroute('**/api/**')
      cold.delayedNativeRedirects = heldRequests
      cold.refreshes = responses.filter(r => r.path === '/auth/refresh').length
    }
    let legacyCache
    if (process.env.PWA_BACKEND_SWITCH) {
      const cacheProbe = await context.newPage()
      const cacheCDP = await context.newCDPSession(cacheProbe)
      await cacheCDP.send('Network.enable')
      const cacheDocuments = []
      cacheCDP.on('Network.responseReceived', ({ type, response }) => {
        if (type === 'Document') cacheDocuments.push({ url: response.url, fromDiskCache: response.fromDiskCache, headers: response.headers })
      })
      // Populate then ordinarily revisit the exact migration URL on the original
      // legacy factory. No route interception or cache disable/clear is involved.
      await cacheProbe.goto(origin + '/auth/login')
      await cacheProbe.goto('about:blank')
      const cached = await cacheProbe.goto(origin + '/auth/login')
      expect((await cached.body()).equals(await readFile(path.join(process.env.PWA_TEST_OLD, 'index.html')))).toBe(true)
      expect(cacheDocuments.at(-1).fromDiskCache).toBe(true)
      legacyCache = cacheDocuments
      await cacheProbe.close()
    }
    // A warm navigation acquires the first installed controller, even without clientsClaim.
    await page.reload()
    await expect(username).toBeVisible()
    await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true)
    const input = await username.elementHandle()
    await username.fill('synthetic-unsaved-pwa-name')
    const baseline = { documents: documents.length, requests: requests.length }
    let native401
    if (process.env.PWA_NATIVE_RACES === '1') {
      const responseStart = responses.length
      const urlBefore = page.url()
      let releaseRefresh
      const refreshGate = new Promise(resolve => { releaseRefresh = resolve })
      let heldRefreshes = 0
      await page.route('**/auth/refresh', async route => {
        heldRefreshes++
        await refreshGate
        await route.continue()
      })
      await page.evaluate(() => {
        window.__pwaNativeRace = Promise.allSettled([
          '/api/system/info', '/api/streamers', '/api/notifications/settings',
        ].map(endpoint => window.__pwaTestClient.request(endpoint, { headers: { Accept: 'application/json' } })))
      })
      await expect.poll(() => responses.slice(responseStart).filter(r => r.path.startsWith('/api/') && r.status === 401).length).toBe(3)
      await expect.poll(() => heldRefreshes).toBe(1)
      releaseRefresh()
      await page.evaluate(() => window.__pwaNativeRace.then(results => {
        if (results.some(result => result.status !== 'rejected' || result.reason.code !== 'auth_lost')) throw new Error('Expected genuine auth-loss errors')
      }))
      await page.unroute('**/auth/refresh')
      await expect(username).toHaveValue('synthetic-unsaved-pwa-name')
      expect(await input.evaluate(n => n.isConnected)).toBe(true)
      expect(documents.length).toBe(baseline.documents)
      expect(page.url()).toBe(urlBefore)
      native401 = responses.slice(responseStart)
      expect(native401.filter(r => r.path === '/auth/refresh')).toEqual([{ path: '/auth/refresh', status: 401 }])
    }
    const oldBytes = await (await context.request.get(origin + '/sw.js')).body()
    await selectBuild(process.env.PWA_TEST_NEW)
    const newBytes = await (await context.request.get(origin + '/sw.js')).body()
    expect(hash(oldBytes)).not.toBe(hash(newBytes))
    await page.evaluate(async () => { await (await navigator.serviceWorker.getRegistration()).update() })
    await expect.poll(() => workers.filter(v => v.status === (expectLoss ? 'activated' : 'installed')).map(v => v.versionId).filter((id, i, a) => a.indexOf(id) === i).length).toBeGreaterThanOrEqual(expectLoss ? 2 : 1)
    // Explicit observation interval after real installation/activation, not router events.
    await page.waitForTimeout(1500)
    let inputStillConnected
    let inputContextDestroyed = false
    try { inputStillConnected = await input.evaluate(n => n.isConnected) }
    catch (error) {
      if (!String(error).includes('Execution context was destroyed')) throw error
      inputStillConnected = false
      inputContextDestroyed = true
    }
    const row = { mobile, cold, legacyCache, native401, oldWorkerHash: hash(oldBytes), newWorkerHash: hash(newBytes), baseline,
      documents, requests, submissions, workers,
      inputStillConnected, inputContextDestroyed, value: await username.inputValue(),
      waiting: await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration()).waiting),
      navigation: await page.evaluate(() => performance.getEntriesByType('navigation').map(e => ({ name: e.name, type: e.type }))),
    }
    results.push(row)
    await writeFile(path.join(output, 'worker-observations.json'), JSON.stringify(results, null, 2))
    expect(row.submissions).toHaveLength(0)
    if (expectLoss) {
      expect(row.documents.length).toBe(baseline.documents + 1)
      expect(row.requests.length).toBe(baseline.requests + 1)
      expect(row.inputStillConnected).toBe(false)
      expect(row.value).toBe('')
      expect(row.navigation[0].type).toBe('reload')
    } else {
      expect(row.documents.length).toBe(baseline.documents)
      expect(row.requests.length).toBe(baseline.requests)
      expect(row.inputStillConnected).toBe(true)
      expect(row.value).toBe('synthetic-unsaved-pwa-name')
      expect(row.waiting).toBe(true)
    }
    if (full) await completeUpgrade(context, page, row, input, documents, requests, traffic, responses)
    if (!full && !expectLoss) {
      // A waiting fixed worker must activate naturally only after legacy clients leave.
      await page.close()
      const fixedWorker = context.serviceWorkers().at(-1)
      await expect.poll(() => fixedWorker.evaluate(() => self.registration.active?.state)).toBe('activated')
      const resumed = await context.newPage()
      const resumedErrors = [], resumedResponses = [], networkDocuments = [], resumedDocuments = [], resumedRequests = []
      resumed.on('domcontentloaded', () => resumedDocuments.push(resumed.url()))
      resumed.on('request', request => {
        if (request.isNavigationRequest() && request.frame() === resumed.mainFrame()) resumedRequests.push(request.url())
      })
      const resumedCDP = await context.newCDPSession(resumed)
      await resumedCDP.send('Network.enable')
      resumedCDP.on('Network.responseReceived', event => { if (event.type === 'Document') networkDocuments.push({ url: event.response.url, status: event.response.status, fromDiskCache: event.response.fromDiskCache, headers: Object.fromEntries(Object.entries(event.response.headers).filter(([key]) => /cache-control|last-modified|etag/i.test(key))) }) })
      resumed.on('pageerror', error => resumedErrors.push(String(error)))
      resumed.on('response', response => resumedResponses.push({ url: response.url(), status: response.status(), fromWorker: response.fromServiceWorker() }))
      const response = await resumed.goto(origin + '/auth/login')
      const resumedIndexMatches = (await response.body()).equals(await readFile(path.join(process.env.PWA_TEST_NEW, 'index.html')))
      await resumed.waitForLoadState('networkidle')
      const directResponse = await context.request.get(origin + '/auth/login')
      const directIndexMatches = (await directResponse.body()).equals(await readFile(path.join(process.env.PWA_TEST_NEW, 'index.html')))
      await writeFile(path.join(output, 'legacy-resumed-diagnostic.json'), JSON.stringify({ resumedIndexMatches, directIndexMatches, networkDocuments, resumedErrors, resumedResponses, html: await resumed.locator('body').innerText() }, null, 2))
      if (process.env.PWA_EXPECT_CACHE_LOSS === '1') {
        expect(resumedIndexMatches).toBe(false)
        expect(directIndexMatches).toBe(true)
        expect(networkDocuments.at(-1).fromDiskCache).toBe(true)
        expect(resumedResponses.filter(response => response.status === 404)).toHaveLength(2)
        await expect(resumed.getByLabel('Username', { exact: true })).toHaveCount(0)
        row.expectedLegacyCacheLoss = { networkDocuments, resumedErrors, resumedResponses }
        await writeFile(path.join(output, 'worker-observations.json'), JSON.stringify(results, null, 2))
        await context.close()
        continue
      }
      await expect(resumed.getByLabel('Username', { exact: true })).toBeVisible()
      await expect.poll(() => resumed.evaluate(async () => !(await navigator.serviceWorker.getRegistration()).waiting)).toBe(true)
      expect((await response.body()).equals(await readFile(path.join(process.env.PWA_TEST_NEW, 'index.html')))).toBe(true)
      row.safeLateActivation = { waiting: false, newDocumentBytes: true, legacyCache,
        networkDocuments, resumedErrors, resumedResponses, resumedDocuments, resumedRequests,
        oldIndexHash: hash(await readFile(path.join(process.env.PWA_TEST_OLD, 'index.html'))),
        newIndexHash: hash(await response.body()), fromWorker: response.fromServiceWorker(),
        navigation: await resumed.evaluate(() => performance.getEntriesByType('navigation').map(e => ({ name: e.name, type: e.type }))),
      }
      expect(resumedErrors).toEqual([])
      expect(resumedResponses.filter(response => response.status >= 400)).toEqual([])
      expect(resumedDocuments).toHaveLength(1)
      expect(resumedRequests).toHaveLength(1)
      expect(networkDocuments.at(-1).fromDiskCache).toBe(false)
      expect(response.fromServiceWorker()).toBe(true)
      expect(response.headers()['cache-control']).toBe('no-store')
    }
    await writeFile(path.join(output, 'worker-observations.json'), JSON.stringify(results, null, 2))
    await context.close()
  }
  console.log(expectLoss ? 'Real factory Desktop/Mobile RED reproduced: activated update discarded input and reloaded document.' : 'Real factory Desktop/Mobile worker waiting preserved input.')
} finally { await browser.close() }
