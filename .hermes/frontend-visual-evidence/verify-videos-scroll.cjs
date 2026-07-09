const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const outDir = path.resolve(__dirname)
const baseUrl = 'http://127.0.0.1:5173/videos'

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true })
  await page.goto(baseUrl, { waitUntil: 'networkidle' })
  await page.waitForSelector('.video-wrapper', { timeout: 10000 })
  const metricsBefore = await page.evaluate(() => ({
    windowScrollY: window.scrollY,
    docScrollHeight: document.documentElement.scrollHeight,
    bodyScrollHeight: document.body.scrollHeight,
    mainScrollTop: document.querySelector('main')?.scrollTop ?? null,
    mainScrollHeight: document.querySelector('main')?.scrollHeight ?? null,
    mainClientHeight: document.querySelector('main')?.clientHeight ?? null,
  }))
  await page.screenshot({ path: path.join(outDir, 'videos-mobile-390x844-viewport-top.png'), fullPage: false })
  await page.evaluate(() => window.scrollTo(0, 760))
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(outDir, 'videos-mobile-390x844-viewport-cards.png'), fullPage: false })
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await page.waitForTimeout(250)
  await page.screenshot({ path: path.join(outDir, 'videos-mobile-390x844-viewport-bottom.png'), fullPage: false })
  const metricsAfter = await page.evaluate(() => ({
    windowScrollY: window.scrollY,
    docScrollHeight: document.documentElement.scrollHeight,
    bodyScrollHeight: document.body.scrollHeight,
    bottomNav: (() => { const r = document.querySelector('.bottom-nav, nav[aria-label="Bottom navigation"]')?.getBoundingClientRect(); return r && { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height) } })(),
    visibleCards: [...document.querySelectorAll('.video-wrapper')].filter((el) => {
      const r = el.getBoundingClientRect()
      return r.bottom > 0 && r.top < window.innerHeight
    }).map((el) => {
      const r = el.getBoundingClientRect()
      return { top: Math.round(r.top), bottom: Math.round(r.bottom), height: Math.round(r.height), text: el.innerText.slice(0, 80) }
    }),
  }))
  const report = {
    screenshots: [
      path.join(outDir, 'videos-mobile-390x844-viewport-top.png'),
      path.join(outDir, 'videos-mobile-390x844-viewport-cards.png'),
      path.join(outDir, 'videos-mobile-390x844-viewport-bottom.png'),
    ],
    metricsBefore,
    metricsAfter,
  }
  const reportPath = path.join(outDir, 'videos-mobile-scroll-report.json')
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ reportPath, ...report }, null, 2))
  await browser.close()
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
