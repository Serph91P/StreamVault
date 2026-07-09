const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const outDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence/dashboard-overhaul'
fs.mkdirSync(outDir, { recursive: true })

async function capture(name, viewport) {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 })
  const messages = []
  page.on('console', (msg) => messages.push({ type: msg.type(), text: msg.text() }))
  page.on('pageerror', (error) => messages.push({ type: 'pageerror', text: error.message }))

  await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('#dashboard-title', { timeout: 10000 })
  await page.waitForTimeout(1000)

  const screenshot = path.join(outDir, `${name}.png`)
  await page.screenshot({ path: screenshot, fullPage: false })

  const text = await page.locator('body').innerText({ timeout: 5000 })
  const firstViewportText = await page.evaluate(() => {
    const nodes = [...document.body.querySelectorAll('h1,h2,h3,p,span,strong,dt,dd,button,a')]
    return nodes
      .filter((node) => {
        const rect = node.getBoundingClientRect()
        return rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight
      })
      .map((node) => node.textContent.trim())
      .filter(Boolean)
      .join(' | ')
  })

  await browser.close()
  return { name, viewport, screenshot, text, firstViewportText, messages }
}

;(async () => {
  const results = []
  results.push(await capture('dashboard-desktop-1440x1000', { width: 1440, height: 1000 }))
  results.push(await capture('dashboard-mobile-390x844', { width: 390, height: 844, isMobile: true }))
  const manifest = path.join(outDir, 'manifest.json')
  fs.writeFileSync(manifest, JSON.stringify({ capturedAt: new Date().toISOString(), url: 'http://127.0.0.1:5173/', results }, null, 2))
  console.log(JSON.stringify({ manifest, results: results.map((r) => ({ name: r.name, viewport: r.viewport, screenshot: r.screenshot, firstViewportText: r.firstViewportText, consoleMessages: r.messages })) }, null, 2))
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
