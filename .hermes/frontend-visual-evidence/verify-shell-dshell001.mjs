import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const require = createRequire('/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/app/frontend/package.json')
const { chromium } = require('playwright')

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:5173/'
const OUT = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence'
fs.mkdirSync(OUT, { recursive: true })
const ROUTE_LABELS = ['Dashboard', 'Streamers', 'Library', 'Subscriptions', 'Settings']

async function assertVisible(locator, label) {
  const visible = await locator.isVisible()
  if (!visible) throw new Error(`${label} is not visible`)
}

async function assertCount(locator, expected, label) {
  const count = await locator.count()
  if (count !== expected) throw new Error(`${label} count ${count} did not match expected ${expected}`)
}

async function setupPage(context) {
  const page = await context.newPage()
  const messages = []
  page.on('console', msg => messages.push({ type: msg.type(), text: msg.text() }))
  await page.goto(BASE_URL, { waitUntil: 'networkidle' })
  await page.waitForSelector('.app-header', { state: 'visible', timeout: 15000 })
  await page.waitForTimeout(500)
  return { page, messages }
}

async function visibleBBox(page, selector) {
  return page.locator(selector).evaluateAll(els => els
    .filter(el => {
      const s = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0
    })
    .map(el => {
      const r = el.getBoundingClientRect()
      const label = el.getAttribute('aria-label') || (el.textContent || '').trim().replace(/\s+/g, ' ')
      return {
        label,
        width: Math.round(r.width),
        height: Math.round(r.height),
        x: Math.round(r.x),
        y: Math.round(r.y),
        tag: el.tagName.toLowerCase(),
        classes: String(el.className)
      }
    }))
}

async function routeProbe(page, navSelector) {
  const results = []
  for (const label of ROUTE_LABELS) {
    await page.locator(`${navSelector} [aria-label="${label}"]`).first().click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(250)
    results.push({ label, url: page.url(), status: 'ok' })
  }
  return results
}

async function screenshot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: true })
  return file
}

function summarizeTargets(result, scope) {
  let minTarget = null
  const offenders = []
  for (const [key, entries] of Object.entries(result[scope])) {
    if (!key.endsWith('_targets') || !Array.isArray(entries)) continue
    for (const entry of entries) {
      const smallest = Math.min(entry.width, entry.height)
      minTarget = minTarget === null ? smallest : Math.min(minTarget, smallest)
      if (entry.width < 44 || entry.height < 44) offenders.push({ group: key, ...entry })
    }
  }
  result[scope].min_touch_target_px = minTarget
  result[scope].touch_target_offenders = offenders
}

const result = { screenshots: {}, desktop: {}, mobile: {}, console: {}, routes: {} }
const browser = await chromium.launch({ headless: true })

const desktopCtx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
const { page: desktop, messages: desktopMessages } = await setupPage(desktopCtx)
await assertVisible(desktop.locator('.sidebar-nav'), 'desktop sidebar')
await assertVisible(desktop.locator('.app-header'), 'desktop app header')
result.screenshots.desktop_expanded = await screenshot(desktop, 'desktop-shell-expanded-1440x900.png')
result.desktop.initial_targets = await visibleBBox(desktop, '.app-header button, .sidebar-nav a, .sidebar-nav button')
result.desktop.nav_labels = await desktop.locator('.sidebar-nav a').evaluateAll(els => els.map(el => el.getAttribute('aria-label') || (el.textContent || '').trim().replace(/\s+/g, ' ')))
result.routes.desktop_sidebar = await routeProbe(desktop, '.sidebar-nav')

await desktop.getByLabel('Collapse sidebar').click()
const desktopUrl = desktop.url()
await desktop.waitForTimeout(400)
result.screenshots.desktop_collapsed = await screenshot(desktop, 'desktop-shell-collapsed-1440x900.png')
result.desktop.collapsed_targets = await visibleBBox(desktop, '.app-header button, .sidebar-nav a, .sidebar-nav button')

await desktop.goto(desktopUrl, { waitUntil: 'networkidle' })
await desktop.getByLabel('Open background queue').click()
await desktop.waitForSelector('#background-queue-panel', { state: 'visible', timeout: 10000 })
result.screenshots.desktop_queue = await screenshot(desktop, 'desktop-background-queue-panel-1440x900.png')
result.desktop.queue_targets = await visibleBBox(desktop, '#background-queue-panel button, .app-header button')
await desktop.getByLabel('Close background queue').click()
await desktop.waitForTimeout(250)

await desktop.getByLabel('Open notifications').click()
await desktop.waitForSelector('#notification-panel', { state: 'visible', timeout: 10000 })
result.screenshots.desktop_notifications = await screenshot(desktop, 'desktop-notification-panel-1440x900.png')
result.desktop.notification_targets = await visibleBBox(desktop, '#notification-panel button, .app-header button')

const mobileCtx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true })
const { page: mobile, messages: mobileMessages } = await setupPage(mobileCtx)
await assertVisible(mobile.locator('.bottom-nav'), 'mobile bottom nav')
await assertCount(mobile.locator('.sidebar-nav'), 0, 'mobile sidebar')
result.screenshots.mobile_shell = await screenshot(mobile, 'mobile-shell-390x844.png')
result.mobile.initial_targets = await visibleBBox(mobile, '.app-header button, .bottom-nav button')
result.mobile.nav_labels = await mobile.locator('.bottom-nav button').evaluateAll(els => els.map(el => el.getAttribute('aria-label') || (el.textContent || '').trim().replace(/\s+/g, ' ')))
result.routes.mobile_bottom_nav = await routeProbe(mobile, '.bottom-nav')

await mobile.getByLabel('Open notifications').click()
await mobile.waitForSelector('#notification-panel', { state: 'visible', timeout: 10000 })
result.screenshots.mobile_notifications = await screenshot(mobile, 'mobile-notification-panel-390x844.png')
result.mobile.notification_targets = await visibleBBox(mobile, '#notification-panel button, .app-header button, .bottom-nav button')
await mobile.keyboard.press('Escape')
await mobile.waitForTimeout(300)

await mobile.getByLabel('Open background queue').click()
await mobile.waitForSelector('#background-queue-panel', { state: 'visible', timeout: 10000 })
result.screenshots.mobile_queue = await screenshot(mobile, 'mobile-background-queue-panel-390x844.png')
result.mobile.queue_targets = await visibleBBox(mobile, '#background-queue-panel button, .app-header button, .bottom-nav button')

result.console.desktop_errors = desktopMessages.filter(m => ['error', 'warning'].includes(m.type))
result.console.mobile_errors = mobileMessages.filter(m => ['error', 'warning'].includes(m.type))
summarizeTargets(result, 'desktop')
summarizeTargets(result, 'mobile')

await browser.close()
fs.writeFileSync(path.join(OUT, 'verify-shell-dshell001-summary.json'), JSON.stringify(result, null, 2))
console.log(JSON.stringify(result, null, 2))
