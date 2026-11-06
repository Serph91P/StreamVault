import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
const { expect } = createRequire(process.env.FRONTEND_ROOT + '/package.json')('@playwright/test')

// Real SPA documents and product APIs only; never fulfill a business request.
export async function verifyShell({ page, context, browser, origin, device }) {
  const proof = { documents: [], returns: [], geometry: [], utilities: false }
  const go = path => page.goto(origin + path)
  const clickOrigin = async target => {
    await page.evaluate(() => document.addEventListener('click', () => { window.__shellClickScroll = scrollY }, { capture: true, once: true }))
    await target.click()
    return page.evaluate(() => window.__shellClickScroll)
  }
  const landmark = async () => {
    await expect(page.locator('main')).toHaveCount(1)
    await expect(page.locator('h1')).toHaveCount(1)
  }
  await go('/?q=synthetic&filter=offline&sort=name-desc&view=list')
  await expect(page.locator('.streamer-card').first()).toBeVisible()
  await landmark()
  const navigation = page.locator(device.isMobile ? '.bottom-nav' : '.sidebar-nav-list')
  await expect(navigation.getByRole('link')).toHaveCount(3)
  await expect(navigation.getByRole('link', { name: 'Kanäle', exact: true })).toHaveAttribute('aria-current', 'page')
  const listOrigin = new URL(page.url()).pathname + new URL(page.url()).search
  const details = page.locator('.streamer-card').filter({ hasText: 'synthetic-channel' }).getByRole('link', { name: 'View details', exact: true })
  await details.scrollIntoViewIfNeeded()
  const listScroll = await clickOrigin(details)
  await expect(page).toHaveURL(/\/streamers\/933/)
  await page.getByRole('tab', { name: 'Videos', exact: true }).click()
  const row = page.locator('.stream-card').filter({ hasText: 'Synthetic recording 933' })
  await row.getByRole('button', { name: 'Expand stream details', exact: true }).click()
  const watch = row.getByRole('button', { name: 'Watch Recording', exact: true })
  await watch.scrollIntoViewIfNeeded()
  const detailOrigin = new URL(page.url()).pathname + new URL(page.url()).search
  const detailScroll = await clickOrigin(watch)
  await expect(page.locator('video')).toBeVisible()
  await page.reload()
  await expect(page.locator('video')).toBeVisible()
  await page.getByRole('button', { name: 'Back to previous page', exact: true }).click()
  await expect(page).toHaveURL(origin + detailOrigin)
  await expect(row.getByRole('button', { name: 'Collapse stream details', exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => scrollY)).toBeCloseTo(detailScroll, 0)
  await page.goForward()
  await expect(page.locator('video')).toBeVisible()
  await page.goBack()
  await expect(row.getByRole('button', { name: 'Collapse stream details', exact: true })).toBeVisible()
  await expect.poll(() => page.evaluate(() => scrollY)).toBeCloseTo(detailScroll, 0)
  await expect(page.locator('.back-button')).toHaveAttribute('href', listOrigin)
  await page.locator('.back-button').click()
  await expect(page).toHaveURL(origin + listOrigin)
  await expect(page.getByRole('textbox', { name: 'Kanäle suchen' })).toHaveValue('synthetic')
  await expect(page.getByLabel('Kanäle sortieren')).toHaveValue('name-desc')
  await expect.poll(() => page.evaluate(() => scrollY)).toBeCloseTo(listScroll, 0)
  proof.returns.push({ origin: listOrigin, detailOrigin, listScroll, detailScroll, expansion: true, playerReload: true })

  for (const path of ['/videos?q=Synthetic&sort=newest&view=list&date=all&duration=&streamer=synthetic-channel', '/activity', '/overview']) {
    await go(path)
    const link = page.getByRole('link', { name: 'Watch Synthetic recording 933', exact: true }).first()
    await link.scrollIntoViewIfNeeded()
    const actualOrigin = new URL(page.url()).pathname + new URL(page.url()).search
    const scroll = await clickOrigin(link)
    await expect(page.locator('video')).toBeVisible()
    await page.getByRole('button', { name: 'Back to previous page', exact: true }).click()
    await expect(page).toHaveURL(origin + actualOrigin)
    await expect.poll(() => page.evaluate(() => scrollY)).toBeCloseTo(scroll, 0)
    await page.goForward()
    await expect(page.locator('video')).toBeVisible()
    await page.goBack()
    await expect(page).toHaveURL(origin + actualOrigin)
    proof.returns.push({ origin: actualOrigin, scroll, browserForwardBack: true })
  }
  await go('/videos/933')
  await expect(page.locator('video')).toBeVisible()
  // A fresh document in an isolated tab has no app predecessor.
  const direct = await context.newPage()
  await direct.goto(origin + '/videos/933')
  await expect(direct.locator('video')).toBeVisible()
  await direct.getByRole('button', { name: 'Back to previous page', exact: true }).click()
  await expect(direct).toHaveURL(origin + '/videos')
  await direct.close()

  for (const theme of ['light', 'dark']) {
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 })
      await page.evaluate(theme => { localStorage.setItem('streamvault-theme', theme); document.documentElement.dataset.theme = theme }, theme)
      for (const [path, card, title, action] of [
        ['/?sort=name-desc', '.streamer-card', '.streamer-name', '.view-details-link'],
        ['/videos', '.video-card', '.video-title', '.video-card-link'],
      ]) {
        await go(path)
        const first = page.locator(card).first()
        await expect(first).toBeVisible()
        await landmark()
        const bounds = []
        for (const target of [first.locator(title), first.locator(action)]) {
          const box = await target.boundingBox()
          assert.ok(box && box.y >= 56 && (width !== 390 || box.y + box.height <= 776), JSON.stringify({ path, width, theme, box, metrics: await target.evaluate(el => ({ class: el.className, font: getComputedStyle(el).fontSize, line: getComputedStyle(el).lineHeight, text: el.textContent, width: el.clientWidth, height: el.clientHeight })) }))
          assert.equal(await target.evaluate(el => el.scrollHeight <= el.clientHeight && el.scrollWidth <= el.clientWidth), true)
          bounds.push(box)
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
        if (path === '/videos') {
          await page.getByRole('button', { name: /^Filters/ }).click()
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
        }
        proof.geometry.push({ path, width, height: 844, theme, bounds })
      }
    }
  }
  await page.setViewportSize({ width: device.width, height: device.height })
  await go('/')
  const more = page.getByRole('button', { name: 'Mehr', exact: true })
  if (device.isMobile) await more.click()
  const utilities = page.getByRole('navigation', { name: 'Werkzeuge und Sitzung' })
  for (const [name, href] of [['Einstellungen', '/settings'], ['System', '/system']]) {
    await expect(utilities.getByRole('link', { name, exact: true })).toHaveAttribute('href', href)
  }
  await expect(utilities.getByRole('button', { name: 'Logout', exact: true })).toBeVisible()
  await utilities.locator('.theme-toggle').click()
  if (device.isMobile) {
    await page.keyboard.press('Escape')
    await expect(more).toBeFocused()
    await more.click()
    await page.locator('.modal-overlay').click({ position: { x: 2, y: 2 } })
    await expect(page.getByRole('dialog', { name: 'Mehr' })).toHaveCount(0)
    await expect(more).toBeFocused()
  }
  await page.keyboard.press('Tab')
  await page.locator('.skip-link').focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
  proof.utilities = true

  // One real document navigation, reload and browser history cycle per router
  // entry. Auth/onboarding guards are expected to redirect completed sessions.
  const routes = ['/', '/streamers', '/streamers/manage', '/streamers/933', '/videos', '/videos/933',
    '/streamer/933/stream/933/watch', '/activity', '/overview', '/add-streamer', '/add-streamer/manual',
    '/add-streamer/import', '/settings?section=recording', '/system', '/admin', '/subscriptions',
    '/auth/login', '/auth/setup', '/welcome', '/onboarding', '/live/synthetic-channel']
  assert.equal(new Set(routes).size, 21)
  const probe = await context.newPage()
  for (const path of routes) {
    // Live uses a separate unauthenticated browser: document/guard compatibility,
    // not a claim of external provider playback or a fulfilled business API.
    const guestContext = path.startsWith('/live/') ? await browser.newContext() : null
    const target = guestContext ? await guestContext.newPage() : probe
    const sentinel = path === '/system' ? '/overview' : '/system'
    const sentinelView = guestContext ? '.login-card' : sentinel === '/system' ? '.system-hub' : '.home-view'
    await target.goto(origin + sentinel)
    await expect(target.locator(sentinelView)).toBeVisible()
    const previous = target.url()
    const ready = async () => {
      if (guestContext) await expect(target.locator('.login-card')).toBeVisible()
      else if (['/auth/login', '/auth/setup', '/welcome', '/onboarding'].includes(path)) {
        await expect(target).toHaveURL(origin + '/')
        await expect(target.locator('.streamers-view')).toBeVisible()
      } else await expect(target).toHaveURL(origin + path)
      await expect(target.locator('main')).toHaveCount(1)
      await expect(target.locator('h1')).toHaveCount(1)
    }
    const response = await target.goto(origin + path)
    assert.equal(response.status(), 200)
    assert.match(response.headers()['content-type'], /text\/html/)
    await ready()
    const final = target.url()
    await target.reload()
    await ready()
    await expect(target).toHaveURL(final)
    await target.goBack()
    await expect(target).toHaveURL(previous)
    await expect(target.locator(sentinelView)).toBeVisible()
    await target.goForward()
    await ready()
    await expect(target).toHaveURL(final)
    proof.documents.push({ requested: path, status: 200, final: new URL(final).pathname + new URL(final).search, reload: true, history: true })
    if (guestContext) await guestContext.close()
  }
  await probe.close()
  assert.equal(proof.documents.length, 21)
  return proof
}
