const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const repoRoot = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final'
const outDir = path.join(repoRoot, '.hermes/frontend-visual-evidence/f-streamers-001')
const baseUrl = process.env.STREAMVAULT_VISUAL_URL || 'http://127.0.0.1:4173'
fs.mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'desktop-1440', width: 1440, height: 900 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'mobile-390', width: 390, height: 844, isMobile: true },
]

async function collect(page, viewport) {
  await page.goto(`${baseUrl}/streamers`, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('.streamers-brief', { timeout: 10000 })
  await page.waitForSelector('.streamer-card', { timeout: 10000 })
  await page.waitForTimeout(500)

  const screenshot = path.join(outDir, `${viewport.name}-streamers.png`)
  await page.screenshot({ path: screenshot, fullPage: true })

  const metrics = await page.evaluate((screenshot) => {
    const text = document.body.innerText
    const summarizeControl = (element) => {
      const rect = element.getBoundingClientRect()
      return {
        label: element.textContent.trim().replace(/\s+/g, ' '),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        top: Math.round(rect.top),
        left: Math.round(rect.left),
        ok: rect.width >= 44 && rect.height >= 44,
      }
    }
    const controls = [...document.querySelectorAll('.filter-tab, .toggle-btn, .btn-action, .refresh-btn, .search-input, .sort-select')]
      .filter((element) => {
        const rect = element.getBoundingClientRect()
        return getComputedStyle(element).display !== 'none' && rect.width > 0 && rect.height > 0
      })
      .map(summarizeControl)

    const cards = [...document.querySelectorAll('.streamer-card')].map((element) => {
      const rect = element.getBoundingClientRect()
      return { width: Math.round(rect.width), height: Math.round(rect.height) }
    })

    return {
      url: location.href,
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      screenshot,
      hasBrief: Boolean(document.querySelector('.streamers-brief')),
      hasSearch: Boolean(document.querySelector('.search-input')),
      hasAddStreamer: text.includes('Add Streamer'),
      hasStatusGrammar: ['Live', 'Recording', 'Offline', 'Last stream', 'VODs'].every((term) => text.includes(term)),
      cardCount: cards.length,
      cards,
      controlCount: controls.length,
      undersizedControls: controls.filter((control) => !control.ok),
      firstViewportText: text.slice(0, 1600),
    }
  }, screenshot)

  return { name: viewport.name, viewport, ...metrics }
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const results = []

  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, isMobile: Boolean(viewport.isMobile), deviceScaleFactor: 1 })
    const messages = []
    page.on('console', (msg) => messages.push({ type: msg.type(), text: msg.text() }))
    page.on('pageerror', (error) => messages.push({ type: 'pageerror', text: error.message }))
    const result = await collect(page, viewport)
    results.push({ ...result, messages })
    await page.close()
  }

  await browser.close()

  const blockers = results.filter((result) => (
    !result.noHorizontalOverflow ||
    !result.hasBrief ||
    !result.hasSearch ||
    !result.hasAddStreamer ||
    !result.hasStatusGrammar ||
    result.cardCount < 1 ||
    result.undersizedControls.length > 0
  ))

  const manifest = { capturedAt: new Date().toISOString(), outDir, results, blocked: blockers.length > 0, blockers }
  fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2))
  console.log(JSON.stringify({ outDir, resultCount: results.length, blocked: manifest.blocked, blockers }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
