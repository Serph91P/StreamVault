// Real browser + live FastAPI/PG/FS. No routes are intercepted or fulfilled.
const { chromium, expect } = require(process.env.STREAMVAULT_PLAYWRIGHT_MODULE)
const fs = require('node:fs')
const path = require('node:path')

async function main() {
  const [baseURL, output, lastId, fixturePath] = process.argv.slice(2)
  const fixture = JSON.parse(fs.readFileSync(fixturePath, 'utf8'))
  fs.mkdirSync(output, { recursive: true })
  const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH, args: ['--no-sandbox'] })
  const report = { browser: browser.version(), mockedRoutes: false, requests: [], pageErrors: [], checks: [], deletedIds: [], failedIds: [] }
  try {
    for (const viewport of [{width:1440,height:900},{width:390,height:844}]) {
      const context = await browser.newContext({ baseURL, viewport, serviceWorkers:'block' })
      const login = await context.request.post('/auth/login', {data:{username:'acceptance-admin',password:'acceptance-password'}})
      expect(login.status()).toBe(200)
      const page = await context.newPage()
      page.on('pageerror', e => report.pageErrors.push(e.message))
      page.on('request', request => {
        const url = new URL(request.url())
        if(url.pathname.startsWith('/api/videos') || url.pathname.startsWith('/api/streams')) report.requests.push({method:request.method(),path:url.pathname,query:url.search})
      })
      await page.goto('/videos')
      await expect(page.locator('.video-card')).toHaveCount(50)
      const first = await page.locator('.video-title').allTextContents()
      await page.getByRole('button',{name:'Next video page'}).click()
      await expect(page).toHaveURL(/page=2/)
      await expect(page.locator('.video-card')).toHaveCount(50)
      const second = await page.locator('.video-title').allTextContents()
      expect(second.some(title=>!first.includes(title))).toBe(true)
      await page.getByRole('textbox',{name:'Search videos'}).fill('Browser video 119')
      await expect(page.locator('.video-card')).toHaveCount(1)
      await expect(page.locator('.video-title')).toHaveText('Browser video 119')
      await page.getByRole('button',{name:'Clear video search'}).click()
      await expect(page.locator('.video-card')).toHaveCount(50)
      await page.getByRole('combobox',{name:'Sort videos'}).selectOption('oldest')
      await expect.poll(async()=>new URL(page.url()).searchParams.get('sort')).toBe('oldest')
      await page.getByRole('button',{name:'Filters',exact:false}).click()
      await page.getByRole('combobox',{name:'Filter videos by streamer'}).selectOption('browser-channel')
      await expect(page.locator('.video-card')).toHaveCount(50)
      await expect(page.locator('.video-title').first()).toHaveText('Browser video 119')
      const filteredFirst=await page.locator('.video-title').allTextContents()
      await page.getByRole('button',{name:'Next video page'}).click()
      await expect(page).toHaveURL(/page=2/)
      await expect(page.locator('.video-title').first()).not.toHaveText(filteredFirst[0])
      const filteredSecond=await page.locator('.video-title').allTextContents()
      expect(filteredSecond).toHaveLength(50)
      await page.getByRole('button',{name:'Next video page'}).click()
      await expect(page).toHaveURL(/page=3/)
      await expect(page.locator('.video-card')).toHaveCount(20-report.deletedIds.length)
      const filteredThird=await page.locator('.video-title').allTextContents()
      expect(new Set([...filteredFirst,...filteredSecond,...filteredThird]).size).toBe(120-report.deletedIds.length)
      await expect(page.getByRole('button',{name:'Next video page'})).toBeDisabled()
      await page.locator('.video-card .video-card-link').first().click()
      await expect(page.locator('video')).toHaveCount(1)
      await page.goBack()
      await expect(page).toHaveURL(/page=3/)
      await expect(page).toHaveURL(/streamer=browser-channel/)
      await expect(page.locator('.video-card')).toHaveCount(filteredThird.length)
      expect(await page.locator('.video-title').allTextContents()).toEqual(filteredThird)
      // Deep player navigation must use one metadata read, never the legacy full catalog.
      await page.goto(`/videos/${lastId}`)
      await expect(page.getByText('Browser video 119',{exact:true}).first()).toBeVisible()
      await expect.poll(async()=>page.locator('video').count()).toBeGreaterThan(0)
      await expect.poll(async()=>page.locator('video').first().evaluate(v=>v.readyState)).toBeGreaterThanOrEqual(1)
      await page.locator('video').first().evaluate(async v=>{ v.muted=true; await v.play() })
      await expect.poll(async()=>page.locator('video').first().evaluate(v=>v.currentTime)).toBeGreaterThan(.1)
      await page.locator('video').first().evaluate(v=>{v.currentTime=2.5})
      await expect.poll(async()=>page.locator('video').first().evaluate(v=>v.currentTime)).toBeGreaterThanOrEqual(2.5)
      await page.screenshot({path:path.join(output,`browser-${viewport.width}.png`),fullPage:true})
      report.checks.push({viewport,firstPage:first.length,secondPage:second.length,thirdPage:filteredThird.length,filteredTotal:120-report.deletedIds.length,historyPage:3,search:1,playerId:Number(lastId)})
      await page.goto('/videos?sort=oldest&streamer=browser-channel')
      await expect(page.locator('.video-card')).toHaveCount(50)
      const selectedLink=await page.locator('.video-card .video-card-link').nth(10).getAttribute('href')
      const deletedId=Number(selectedLink.match(/\/stream\/(\d+)\/watch/)[1])
      const partial = viewport.width === 390
      const secondLink=partial ? await page.locator('.video-card .video-card-link').nth(11).getAttribute('href') : null
      const successId=partial ? Number(secondLink.match(/\/stream\/(\d+)\/watch/)[1]) : deletedId
      await page.getByRole('button',{name:'Select',exact:true}).click()
      await page.locator('.video-card .video-card-link').nth(10).click()
      if (partial) {
        await page.locator('.video-card .video-card-link').nth(11).click()
        expect(deletedId).toBe(fixture.protectedId)
      }
      try {
        await page.getByRole('button',{name:`Delete (${partial ? 2 : 1})`,exact:true}).click()
        await page.getByRole('button',{name:'Yes, delete',exact:true}).click()
        if (partial) {
          await expect(page.locator('.delete-error')).toBeVisible()
          await expect(page.getByRole('dialog').getByText(/This will delete 1 selected video /)).toBeVisible()
          await expect(page.locator('.delete-error')).toContainText('1 deleted; 1 failed.')
          report.failedIds.push(deletedId)
          await page.screenshot({path:path.join(output,'partial-delete-mobile.png'),fullPage:true})
          await page.getByRole('button',{name:'No, keep videos',exact:true}).click()
          await expect(page.getByRole('button',{name:'Delete (1)',exact:true})).toBeVisible()
        }
        await expect(page.getByRole('heading',{name:'Delete selected videos?',exact:true})).toHaveCount(0)
        await expect(page.locator('.video-card')).toHaveCount(50)
        report.deletedIds.push(successId)
      } finally { /* Fixture DB fault is removed by the Python owner. */ }
      await context.close()
    }
    expect(report.pageErrors).toEqual([])
    expect(report.requests.some(r=>r.path===`/api/videos/${lastId}/metadata`)).toBe(true)
    expect(report.requests.some(r=>r.path==='/api/videos')).toBe(false)
    report.status='passed'
  } finally {
    await browser.close()
    fs.writeFileSync(path.join(output,'browser.json'),JSON.stringify(report,null,2)+'\n')
  }
}
main().catch(error=>{console.error(error);process.exitCode=1})
