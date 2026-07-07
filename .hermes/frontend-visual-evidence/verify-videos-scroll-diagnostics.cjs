const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')
const outDir = path.resolve(__dirname)

async function snapshotScroll(page, label) {
  return page.evaluate((label) => {
    const all = [
      ['html', document.documentElement],
      ['body', document.body],
      ['app', document.querySelector('.app')],
      ['main', document.querySelector('main')],
    ].filter(([, el]) => el)
    return {
      label,
      windowScrollY: window.scrollY,
      containers: all.map(([name, el]) => ({
        name,
        scrollTop: el.scrollTop,
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        overflowY: getComputedStyle(el).overflowY,
      })),
      firstVisibleCards: [...document.querySelectorAll('.video-wrapper')].filter((el) => {
        const r = el.getBoundingClientRect()
        return r.bottom > 0 && r.top < window.innerHeight
      }).map((el) => {
        const r = el.getBoundingClientRect()
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), text: el.innerText.slice(0, 80) }
      }).slice(0, 4),
    }
  }, label)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true })
  await page.goto('http://127.0.0.1:5173/videos', { waitUntil: 'networkidle' })
  await page.waitForSelector('.video-wrapper', { timeout: 10000 })
  const results = []
  results.push(await snapshotScroll(page, 'initial'))
  await page.mouse.wheel(0, 900)
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(outDir, 'videos-mobile-390x844-after-wheel.png'), fullPage: false })
  results.push(await snapshotScroll(page, 'after-wheel'))
  await page.evaluate(() => { document.body.scrollTop = 900; document.documentElement.scrollTop = 900; const app = document.querySelector('.app'); if (app) app.scrollTop = 900 })
  await page.waitForTimeout(300)
  await page.screenshot({ path: path.join(outDir, 'videos-mobile-390x844-after-programmatic-scroll.png'), fullPage: false })
  results.push(await snapshotScroll(page, 'after-programmatic'))
  await browser.close()
  const reportPath = path.join(outDir, 'videos-scroll-diagnostics.json')
  fs.writeFileSync(reportPath, JSON.stringify(results, null, 2))
  console.log(JSON.stringify({ reportPath, results }, null, 2))
}
main().catch((e) => { console.error(e); process.exit(1) })
