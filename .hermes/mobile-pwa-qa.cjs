const { chromium, devices } = require('/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/app/frontend/node_modules/playwright')
const fs = require('fs')
const path = require('path')

const baseUrl = process.env.BASE_URL || 'http://127.0.0.1:4173'
const evidenceDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence/mobile-pwa-qa'
fs.mkdirSync(evidenceDir, { recursive: true })

const results = []
const notes = []

async function record(name, fn) {
  try {
    const value = await fn()
    results.push({ name, status: 'pass', value })
  } catch (error) {
    results.push({ name, status: 'fail', value: error.message })
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] })
  const context = await browser.newContext({
    ...devices['Pixel 7'],
    baseURL: baseUrl,
    serviceWorkers: 'allow',
  })

  await context.addInitScript(() => {
    window.__permissionCalls = 0
    window.__permissionLog = []
    window.__permissionValue = 'default'
    const patchNotification = () => {
      if (!('Notification' in window) || window.Notification.__streamVaultPatched) return
      const patched = window.Notification
      const original = patched.requestPermission?.bind(patched)
      try {
        Object.defineProperty(patched, 'permission', {
          configurable: true,
          get: () => window.__permissionValue,
        })
      } catch {}
      patched.requestPermission = async (...args) => {
        window.__permissionCalls += 1
        window.__permissionLog.push({ at: Date.now(), args: args.length })
        if (typeof original === 'function') {
          try {
            const result = await original(...args)
            window.__permissionValue = result
            return result
          } catch {
            window.__permissionValue = 'denied'
            return 'denied'
          }
        }
        window.__permissionValue = 'denied'
        return 'denied'
      }
      patched.__streamVaultPatched = true
    }
    patchNotification()
  })

  const page = await context.newPage()
  page.on('console', msg => {
    const text = msg.text()
    if (/Mock mode|WebSocket|Service Worker|Push subscription|Auth check|Failed/i.test(text)) {
      notes.push(`[console:${msg.type()}] ${text}`)
    }
  })
  page.on('pageerror', error => notes.push(`[pageerror] ${error.message}`))

  await page.route('**/auth/**', async route => {
    const url = route.request().url()
    if (url.includes('/auth/setup')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ setup_completed: true, welcome_completed: true }) })
    }
    if (url.includes('/auth/check')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ authenticated: true, user: { username: 'demo' } }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })
  await page.route('**/api/push/vapid-public-key', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ publicKey: null }) }))
  await page.route('**/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: [], notifications: [], settings: {}, ok: true }) }))

  await record('PWA settings route opens on mobile without login redirect', async () => {
    await page.goto('/settings?section=pwa', { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: 'PWA & Mobile' }).first().waitFor({ timeout: 10000 })
    const url = page.url()
    if (!url.includes('/settings')) throw new Error(`unexpected url ${url}`)
    await page.screenshot({ path: path.join(evidenceDir, 'settings-pwa-mobile.png'), fullPage: true })
    return url
  })

  await record('No blind notification permission prompt on page load', async () => {
    await page.waitForTimeout(1000)
    const calls = await page.evaluate(() => window.__permissionCalls)
    if (calls !== 0) throw new Error(`Notification.requestPermission called ${calls} times before user action`)
    return `calls=${calls}`
  })

  await record('Push permission priming requires review before browser permission', async () => {
    await page.getByRole('button', { name: /Review first/i }).click()
    await page.getByText('Browser permission is requested only after you press Allow notifications below.').waitFor({ timeout: 5000 })
    let calls = await page.evaluate(() => window.__permissionCalls)
    if (calls !== 0) throw new Error(`permission requested during primer review: ${calls}`)
    await page.getByRole('button', { name: /Allow notifications/i }).click()
    await page.waitForTimeout(500)
    calls = await page.evaluate(() => window.__permissionCalls)
    if (calls !== 1) throw new Error(`expected one explicit permission request after Allow notifications, got ${calls}`)
    return `calls=${calls}`
  })

  await record('Bottom navigation is visible and route tabs are reachable', async () => {
    const nav = page.locator('nav.bottom-nav')
    await nav.waitFor({ timeout: 5000 })
    const navBox = await nav.boundingBox()
    if (!navBox || navBox.height < 60) throw new Error(`bottom nav missing or too small: ${JSON.stringify(navBox)}`)
    const tabs = ['Dashboard', 'Streamers', 'Library', 'Subscriptions', 'Settings']
    for (const label of tabs) {
      await page.getByRole('button', { name: label }).click()
      await page.waitForTimeout(300)
      if (page.url().includes('/auth/login')) throw new Error(`${label} redirected to login`)
    }
    await page.screenshot({ path: path.join(evidenceDir, 'bottom-nav-routes.png'), fullPage: false })
    return `height=${Math.round(navBox.height)}, tabs=${tabs.join(',')}`
  })

  await record('Offline and reconnect UI appears in mobile shell', async () => {
    await page.goto('/settings?section=pwa', { waitUntil: 'networkidle' })
    await context.setOffline(true)
    await page.evaluate(() => window.dispatchEvent(new Event('offline')))
    await page.getByText(/Offline mode|You are offline/).first().waitFor({ timeout: 5000 })
    const offlineText = await page.locator('body').innerText()
    await page.screenshot({ path: path.join(evidenceDir, 'offline-mobile.png'), fullPage: false })
    await context.setOffline(false)
    await page.evaluate(() => window.dispatchEvent(new Event('online')))
    await page.waitForTimeout(500)
    if (!/Offline mode|You are offline/.test(offlineText)) throw new Error('offline copy not found')
    return 'offline copy visible and online event recovered without crash'
  })

  await record('Runtime safe-area layout uses fixed bottom navigation', async () => {
    const style = await page.locator('nav.bottom-nav').evaluate(el => {
      const s = getComputedStyle(el)
      return { position: s.position, bottom: s.bottom, height: s.height, paddingBottom: s.paddingBottom, zIndex: s.zIndex }
    })
    if (style.position !== 'fixed') throw new Error(`expected fixed nav, got ${JSON.stringify(style)}`)
    return JSON.stringify(style)
  })

  await record('Guided install prompt waits for installability event and links to setup guide', async () => {
    await page.goto('/', { waitUntil: 'networkidle' })
    await page.evaluate(() => localStorage.removeItem('pwaInstallDismissed'))
    await page.evaluate(() => {
      const event = new Event('beforeinstallprompt', { cancelable: true })
      event.prompt = async () => {}
      event.userChoice = Promise.resolve({ outcome: 'dismissed' })
      window.dispatchEvent(event)
    })
    await page.getByText('Install StreamVault App').waitFor({ timeout: 5000 })
    await page.getByRole('button', { name: /Setup guide/i }).click()
    await page.getByRole('heading', { name: 'PWA & Mobile' }).first().waitFor({ timeout: 5000 })
    if (!page.url().includes('/settings?section=pwa')) throw new Error(`setup guide did not navigate to PWA settings: ${page.url()}`)
    return page.url()
  })

  const sw = await page.evaluate(async () => {
    if (!('serviceWorker' in navigator)) return { supported: false }
    const registrations = await navigator.serviceWorker.getRegistrations()
    return { supported: true, count: registrations.length, scopes: registrations.map(r => r.scope) }
  })
  notes.push(`serviceWorker=${JSON.stringify(sw)}`)

  await browser.close()

  const failed = results.filter(r => r.status === 'fail')
  console.log(JSON.stringify({ baseUrl, device: 'Pixel 7 emulation via Playwright Chromium', results, notes, failed: failed.length }, null, 2))
  if (failed.length) process.exit(1)
}

main().catch(error => {
  console.error(error)
  process.exit(1)
})
