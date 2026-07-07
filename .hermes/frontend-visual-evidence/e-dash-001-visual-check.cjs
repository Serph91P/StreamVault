const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const outDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence/e-dash-001'
fs.mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1024', width: 1024, height: 768 },
  { name: 'desktop-1440', width: 1440, height: 900 }
]

function roundRect(rect) {
  if (!rect) return null
  return {
    x: Math.round(rect.x),
    y: Math.round(rect.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    top: Math.round(rect.top),
    right: Math.round(rect.right),
    bottom: Math.round(rect.bottom),
    left: Math.round(rect.left)
  }
}

async function collectMetrics(page, viewportName) {
  return page.evaluate((viewportName) => {
    const rect = (selector) => {
      const el = document.querySelector(selector)
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x, y: r.y, width: r.width, height: r.height, top: r.top, right: r.right, bottom: r.bottom, left: r.left }
    }

    const text = (selector) => document.querySelector(selector)?.textContent?.trim().replace(/\s+/g, ' ') || ''
    const visible = (selector) => {
      const el = document.querySelector(selector)
      if (!el) return false
      const r = el.getBoundingClientRect()
      return getComputedStyle(el).display !== 'none' && r.width > 0 && r.height > 0
    }

    const targets = [...document.querySelectorAll('.hero-action, .brief-primary-action, .recording-card-actions a, .panel-text-button')]
      .filter((el) => {
        const r = el.getBoundingClientRect()
        return getComputedStyle(el).display !== 'none' && r.width > 0 && r.height > 0
      })
      .map((el) => {
        const r = el.getBoundingClientRect()
        return {
          label: el.textContent.trim().replace(/\s+/g, ' '),
          width: Math.round(r.width),
          height: Math.round(r.height),
          ok: r.width >= 44 && r.height >= 36
        }
      })

    const briefLabels = [...document.querySelectorAll('.brief-item-label')].map((el) => el.textContent.trim())
    const firstViewportText = document.body.innerText.slice(0, 1800)

    return {
      viewportName,
      url: location.href,
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      briefVisible: visible('.dashboard-brief'),
      summaryVisible: visible('.summary-section'),
      livePanelPresent: Boolean(document.querySelector('#live-section-title')),
      recordingPanelPresent: Boolean(document.querySelector('#recordings-section-title')),
      queuePanelPresent: Boolean(document.querySelector('#queue-section-title')),
      failuresPanelPresent: Boolean(document.querySelector('#failures-section-title')),
      activityPanelPresent: Boolean(document.querySelector('#activity-section-title')),
      briefLabels,
      headline: text('#dashboard-brief-title'),
      heroRect: rect('.dashboard-hero'),
      briefRect: rect('.dashboard-brief'),
      summaryRect: rect('.summary-section'),
      targetCount: targets.length,
      undersizedTargets: targets.filter((target) => !target.ok),
      firstViewportHasCoreTerms: ['Live', 'Recording', 'Queue', 'Errors', 'Recent activity'].every((term) => firstViewportText.includes(term))
    }
  }, viewportName)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const results = []

  for (const viewport of viewports) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 })
    await page.goto('http://127.0.0.1:4173/', { waitUntil: 'networkidle' })
    await page.screenshot({ path: path.join(outDir, `${viewport.name}-dashboard.png`), fullPage: true })
    const metrics = await collectMetrics(page, viewport.name)
    results.push(metrics)
    await page.close()
  }

  await browser.close()
  const rounded = results.map((result) => ({
    ...result,
    heroRect: roundRect(result.heroRect),
    briefRect: roundRect(result.briefRect),
    summaryRect: roundRect(result.summaryRect)
  }))
  const blockers = rounded.filter((result) => (
    !result.noHorizontalOverflow ||
    !result.briefVisible ||
    !result.summaryVisible ||
    !result.livePanelPresent ||
    !result.recordingPanelPresent ||
    !result.queuePanelPresent ||
    !result.failuresPanelPresent ||
    !result.activityPanelPresent ||
    result.undersizedTargets.length > 0 ||
    result.briefLabels.length !== 5 ||
    !result.firstViewportHasCoreTerms
  ))

  fs.writeFileSync(path.join(outDir, 'metrics.json'), JSON.stringify(rounded, null, 2))
  console.log(JSON.stringify({ outDir, viewports: rounded.length, blocked: blockers.length > 0, blockers }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
