const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const repoRoot = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final'
const outDir = path.join(repoRoot, '.hermes/frontend-visual-evidence/g-detail-001')
const baseUrl = process.env.STREAMVAULT_VISUAL_URL || 'http://127.0.0.1:4173'
fs.mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'mobile-390', width: 390, height: 844, isMobile: true },
]

const tabs = ['overview', 'videos', 'settings', 'events']

async function captureTab(page, viewport, tabId, streamerId) {
  const url = `${baseUrl}/streamers/${streamerId}`
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('.compact-header', { timeout: 10000 })
  await page.waitForTimeout(500)

  // Click the tab
  const tabs = page.locator('.cockpit-tab')
  const tabCount = await tabs.count()
  for (let i = 0; i < tabCount; i++) {
    const text = await tabs.nth(i).innerText()
    if (text.toLowerCase().includes(tabId) || text.toLowerCase().includes(tabId.replace('_', ' '))) {
      await tabs.nth(i).click()
      break
    }
  }
  await page.waitForTimeout(500)

  const screenshot = path.join(outDir, `${viewport.name}-tab-${tabId}-streamer-${streamerId}.png`)
  await page.screenshot({ path: screenshot, fullPage: true })

  // Check touch targets for tab buttons
  const tabControls = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('.cockpit-tab')]
    return tabs.map(tab => {
      const rect = tab.getBoundingClientRect()
      return {
        text: tab.textContent.trim().replace(/\s+/g, ' '),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        ok: rect.width >= 44 && rect.height >= 44,
      }
    })
  })

  // Check key action buttons touch targets
  const actionButtons = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('.btn-action, .compact-header button, .danger-zone-card button, .back-button')]
    return buttons.filter(el => {
      const rect = el.getBoundingClientRect()
      return getComputedStyle(el).display !== 'none' && rect.width > 0 && rect.height > 0
    }).map(el => {
      const rect = el.getBoundingClientRect()
      return {
        text: el.textContent.trim().replace(/\s+/g, ' '),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        ok: rect.width >= 44 && rect.height >= 44,
      }
    })
  })

  const metrics = await page.evaluate((screenshot) => {
    return {
      url: location.href,
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      screenshot,
      hasCompactHeader: Boolean(document.querySelector('.compact-header')),
      hasAvatar: Boolean(document.querySelector('.compact-avatar')),
      hasTabs: Boolean(document.querySelector('.cockpit-tabs')),
      hasTabContent: Boolean(document.querySelector('.cockpit-panel')),
      firstViewportText: document.body.innerText.slice(0, 1200),
    }
  }, screenshot)

  return { name: `${viewport.name}-tab-${tabId}`, viewport, tabId, tabControls, actionButtons, ...metrics }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const results = []

  for (const viewport of viewports) {
    const page = await browser.newPage({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: Boolean(viewport.isMobile),
      deviceScaleFactor: 1,
    })
    const messages = []
    page.on('console', (msg) => messages.push({ type: msg.type(), text: msg.text() }))
    page.on('pageerror', (error) => messages.push({ type: 'pageerror', text: error.message }))

    for (const tabId of tabs) {
      const result = await captureTab(page, viewport, tabId, 1)
      results.push({ ...result, messages })
    }
    await page.close()
  }

  await browser.close()

  // Check for blockers
  const blockers = results.filter(result => (
    !result.noHorizontalOverflow ||
    !result.hasCompactHeader ||
    !result.hasAvatar ||
    !result.hasTabs ||
    !result.hasTabContent
  ))

  // Check for undersized controls across all results
  const undersizedControlResults = results.filter(r => r.tabControls.some(c => !c.ok))
  if (undersizedControlResults.length > 0) {
    blockers.push({
      type: 'undersized_tab_controls',
      detail: undersizedControlResults.map(r => ({
        viewport: r.viewport.name,
        tab: r.tabId,
        controls: r.tabControls.filter(c => !c.ok),
      })),
    })
  }

  const manifest = {
    capturedAt: new Date().toISOString(),
    outDir,
    results,
    blocked: blockers.length > 0,
    blockers,
  }
  fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2))
  console.log(JSON.stringify({ outDir, resultCount: results.length, blocked: manifest.blocked, blockers: manifest.blockers }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
