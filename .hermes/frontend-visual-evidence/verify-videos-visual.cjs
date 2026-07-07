const fs = require('node:fs')
const path = require('node:path')
const { chromium } = require('playwright')

const baseUrl = process.env.QA_BASE_URL || 'http://127.0.0.1:5173/videos'
const outDir = path.resolve(__dirname)
fs.mkdirSync(outDir, { recursive: true })

const viewports = [
  { name: 'desktop-1440x900', width: 1440, height: 900 },
  { name: 'tablet-768x1024', width: 768, height: 1024 },
  { name: 'mobile-390x844', width: 390, height: 844 },
  { name: 'narrow-360x740', width: 360, height: 740 },
]

async function collectLayout(page, label) {
  return page.evaluate((label) => {
    const rect = (el) => {
      const r = el.getBoundingClientRect()
      return {
        x: Math.round(r.x),
        y: Math.round(r.y),
        width: Math.round(r.width),
        height: Math.round(r.height),
      }
    }
    const wrappers = [...document.querySelectorAll('.video-wrapper')]
    const controls = [...document.querySelectorAll('.controls-bar button, .controls-bar select, .search-input')]
    const rowTops = [...new Set(wrappers.map((el) => Math.round(el.getBoundingClientRect().top)))].sort((a, b) => a - b)
    const firstRowTop = rowTops[0]
    const firstRowCount = wrappers.filter((el) => Math.round(el.getBoundingClientRect().top) === firstRowTop).length
    const tapTargets = controls.map((el) => ({
      label: el.getAttribute('aria-label') || el.textContent.trim() || el.tagName,
      ...rect(el),
    }))
    return {
      label,
      url: location.href,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      document: {
        scrollWidth: document.documentElement.scrollWidth,
        scrollHeight: document.documentElement.scrollHeight,
        bodyScrollWidth: document.body.scrollWidth,
      },
      hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth,
      cards: wrappers.length,
      firstRowCount,
      controlsBar: rect(document.querySelector('.controls-bar')),
      searchBox: rect(document.querySelector('.search-box')),
      tapTargets,
      visibleText: document.body.innerText.slice(0, 1200),
    }
  }, label)
}

async function injectMediaStateSamples(page) {
  await page.evaluate(() => {
    const root = document.querySelector('.videos-view')
    const setup = root && root.__vueParentComponent && root.__vueParentComponent.setupState
    if (!setup || !Array.isArray(setup.videos)) return false
    const extras = [
      {
        id: 9001,
        streamer_id: 1,
        streamer_name: 'qa_corrupt',
        title: 'QA failed corrupt media sample',
        category_name: 'QA State',
        duration: 0,
        file_size: 0,
        recorded_at: null,
        thumbnail_url: '/missing-thumbnail-qa.jpg',
        status: 'failed',
      },
      {
        id: 9002,
        streamer_name: 'qa_missing_details',
        title: 'QA missing playback details sample',
        category_name: 'QA State',
        duration: 124,
        file_size: 1024,
        recorded_at: null,
        thumbnail_url: null,
        status: 'ready',
      },
      {
        id: 9003,
        streamer_id: 1,
        streamer_name: 'qa_processing',
        title: 'QA low data processing sample',
        category_name: 'QA State',
        duration: 0,
        file_size: 0,
        recorded_at: new Date().toISOString(),
        thumbnail_url: null,
        status: 'processing',
      },
    ]
    setup.videos = [...extras, ...setup.videos.filter((video) => video.id < 9000)]
    setup.sortBy = 'newest'
    setup.searchQuery = 'QA'
    setup.filterStreamer = ''
    setup.filterDate = 'all'
    setup.filterDuration = ''
    setup.viewMode = 'grid'
    return true
  })
  await page.waitForTimeout(600)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const report = {
    baseUrl,
    generatedAt: new Date().toISOString(),
    screenshots: [],
    layouts: [],
    console: [],
  }

  for (const vp of viewports) {
    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1 })
    page.on('console', (msg) => report.console.push({ viewport: vp.name, type: msg.type(), text: msg.text() }))
    page.on('pageerror', (err) => report.console.push({ viewport: vp.name, type: 'pageerror', text: err.message }))
    await page.goto(baseUrl, { waitUntil: 'networkidle' })
    await page.waitForSelector('.video-wrapper', { timeout: 10000 })

    const gridPath = path.join(outDir, `videos-${vp.name}-grid.png`)
    await page.screenshot({ path: gridPath, fullPage: true })
    report.screenshots.push(gridPath)
    report.layouts.push(await collectLayout(page, `${vp.name} grid`))

    await page.getByLabel('Show videos as list').click()
    await page.waitForTimeout(250)
    const listPath = path.join(outDir, `videos-${vp.name}-list.png`)
    await page.screenshot({ path: listPath, fullPage: true })
    report.screenshots.push(listPath)
    report.layouts.push(await collectLayout(page, `${vp.name} list`))

    if (vp.name.startsWith('mobile') || vp.name.startsWith('narrow')) {
      await page.getByText('Filters').click()
      await page.waitForTimeout(250)
      const filtersPath = path.join(outDir, `videos-${vp.name}-filters-open.png`)
      await page.screenshot({ path: filtersPath, fullPage: true })
      report.screenshots.push(filtersPath)
      report.layouts.push(await collectLayout(page, `${vp.name} filters-open`))

      await page.getByPlaceholder('Search videos by title or streamer...').fill('no-video-results-qa')
      await page.waitForTimeout(250)
      const emptyPath = path.join(outDir, `videos-${vp.name}-empty-filter.png`)
      await page.screenshot({ path: emptyPath, fullPage: true })
      report.screenshots.push(emptyPath)
      report.layouts.push(await collectLayout(page, `${vp.name} empty-filter`))
    }

    if (vp.name === 'desktop-1440x900' || vp.name === 'mobile-390x844') {
      await page.reload({ waitUntil: 'networkidle' })
      await page.waitForSelector('.video-wrapper', { timeout: 10000 })
      await injectMediaStateSamples(page)
      const statePath = path.join(outDir, `videos-${vp.name}-media-states.png`)
      await page.screenshot({ path: statePath, fullPage: true })
      report.screenshots.push(statePath)
      report.layouts.push(await collectLayout(page, `${vp.name} media-states`))
    }

    if (vp.name === 'mobile-390x844') {
      await page.reload({ waitUntil: 'networkidle' })
      await page.waitForSelector('.video-wrapper', { timeout: 10000 })
      await page.getByText('Select').click()
      await page.locator('.select-checkbox input').first().check({ force: true })
      await page.waitForTimeout(250)
      const selectPath = path.join(outDir, `videos-${vp.name}-select-mode.png`)
      await page.screenshot({ path: selectPath, fullPage: true })
      report.screenshots.push(selectPath)
      report.layouts.push(await collectLayout(page, `${vp.name} select-mode`))
    }

    await page.close()
  }

  await browser.close()

  const summaryPath = path.join(outDir, 'videos-visual-verification-report.json')
  fs.writeFileSync(summaryPath, JSON.stringify(report, null, 2))
  console.log(JSON.stringify({ summaryPath, screenshots: report.screenshots, layouts: report.layouts.map((l) => ({ label: l.label, viewport: l.viewport, cards: l.cards, firstRowCount: l.firstRowCount, hasHorizontalOverflow: l.hasHorizontalOverflow, scrollWidth: l.document.scrollWidth })) }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
