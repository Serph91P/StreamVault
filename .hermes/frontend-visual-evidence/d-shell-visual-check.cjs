const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const outDir = '/opt/data/workspace/github_repos/StreamVault-frontend-product-overhaul-final/.hermes/frontend-visual-evidence/d-shell-001'
fs.mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'mobile-390', width: 390, height: 844 },
  { name: 'tablet-768', width: 768, height: 1024 },
  { name: 'desktop-1024', width: 1024, height: 768 },
  { name: 'desktop-1280', width: 1280, height: 720 },
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
    const rect = (el) => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: r.x, y: r.y, width: r.width, height: r.height, top: r.top, right: r.right, bottom: r.bottom, left: r.left }
    }
    const sizeRows = [...document.querySelectorAll('.header-actions button, .bottom-nav .nav-tab, .sidebar-nav-item, .sidebar-toggle')]
      .filter((el) => {
        const r = el.getBoundingClientRect()
        return getComputedStyle(el).display !== 'none' && r.width > 0 && r.height > 0
      })
      .map((el) => {
        const r = el.getBoundingClientRect()
        return {
          label: el.getAttribute('aria-label') || el.textContent.trim().replace(/\s+/g, ' '),
          className: el.className.toString(),
          width: Math.round(r.width),
          height: Math.round(r.height),
          ok: r.width >= 44 && r.height >= 44
        }
      })
    const nav = document.querySelector('.bottom-nav')
    const main = document.querySelector('.main-content')
    const header = document.querySelector('.app-header')
    const sidebar = document.querySelector('.sidebar-nav')
    const navRect = rect(nav)
    const mainRect = rect(main)
    const headerRect = rect(header)
    const sidebarRect = rect(sidebar)
    const mainStyle = main ? getComputedStyle(main) : null
    return {
      viewportName,
      url: location.href,
      documentWidth: document.documentElement.scrollWidth,
      viewportWidth: window.innerWidth,
      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
      headerRect,
      sidebarRect,
      bottomNavRect: navRect,
      mainRect,
      mainPaddingTop: mainStyle ? mainStyle.paddingTop : null,
      mainPaddingBottom: mainStyle ? mainStyle.paddingBottom : null,
      targetCount: sizeRows.length,
      undersizedTargets: sizeRows.filter((row) => !row.ok),
      sampledTargets: sizeRows.slice(0, 12),
      bottomNavVisible: Boolean(nav && getComputedStyle(nav).display !== 'none' && navRect && navRect.height > 0),
      sidebarVisible: Boolean(sidebar && getComputedStyle(sidebar).display !== 'none' && sidebarRect && sidebarRect.width > 0),
      utilityLabels: [...document.querySelectorAll('.header-actions button')].map((el) => el.textContent.trim().replace(/\s+/g, ' '))
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

    if (viewport.width >= 1024) {
      await page.getByLabel('Notifications').click()
      await page.screenshot({ path: path.join(outDir, `${viewport.name}-notifications.png`), fullPage: true })
      await page.keyboard.press('Escape')
      await page.getByLabel('Open background jobs').click()
      await page.screenshot({ path: path.join(outDir, `${viewport.name}-queue.png`), fullPage: true })
    }

    await page.close()
  }
  await browser.close()
  const rounded = results.map((result) => ({
    ...result,
    headerRect: roundRect(result.headerRect),
    sidebarRect: roundRect(result.sidebarRect),
    bottomNavRect: roundRect(result.bottomNavRect),
    mainRect: roundRect(result.mainRect)
  }))
  fs.writeFileSync(path.join(outDir, 'metrics.json'), JSON.stringify(rounded, null, 2))
  const blocked = rounded.filter((r) => !r.noHorizontalOverflow || r.undersizedTargets.length > 0)
  console.log(JSON.stringify({ outDir, viewports: rounded.length, blocked: blocked.length > 0, blockers: blocked }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
