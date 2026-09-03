import { expect, test } from '@playwright/test'
import type { CDPSession, Locator, Page } from '@playwright/test'

interface GestureTelemetry {
  routeChanges: number
  menuOpenings: number
  expansions: number
  ripples: number
  vibrations: number
  overflowClicks: number
  detailClicks: number
  expandClicks: number
  globalMainTouchListeners: Record<'touchstart' | 'touchmove' | 'touchend', number>
}

async function installGestureTelemetry(page: Page) {
  await page.addInitScript(() => {
    const telemetry: GestureTelemetry = {
      routeChanges: 0,
      menuOpenings: 0,
      expansions: 0,
      ripples: 0,
      vibrations: 0,
      overflowClicks: 0,
      detailClicks: 0,
      expandClicks: 0,
      globalMainTouchListeners: { touchstart: 0, touchmove: 0, touchend: 0 },
    }

    Object.defineProperty(window, '__gestureTelemetry', { value: telemetry })

    const touchTypes = new Set(['touchstart', 'touchmove', 'touchend'])
    const originalAddEventListener = EventTarget.prototype.addEventListener
    EventTarget.prototype.addEventListener = function (type, listener, options) {
      if (this instanceof HTMLElement && this.tagName === 'MAIN' && touchTypes.has(type)) {
        telemetry.globalMainTouchListeners[type as keyof typeof telemetry.globalMainTouchListeners] += 1
      }
      return originalAddEventListener.call(this, type, listener, options)
    }

    let currentRoute = `${location.pathname}${location.search}${location.hash}`
    const recordRoute = (url?: string | URL | null) => {
      if (url == null) return
      const next = new URL(String(url), location.href)
      const nextRoute = `${next.pathname}${next.search}${next.hash}`
      if (nextRoute !== currentRoute) telemetry.routeChanges += 1
      currentRoute = nextRoute
    }

    const originalPushState = history.pushState
    history.pushState = function (...args) {
      recordRoute(args[2])
      return originalPushState.apply(this, args)
    }
    const originalReplaceState = history.replaceState
    history.replaceState = function (...args) {
      recordRoute(args[2])
      return originalReplaceState.apply(this, args)
    }
    window.addEventListener('popstate', () => recordRoute(location.href))
    window.addEventListener('hashchange', () => recordRoute(location.href))
    document.addEventListener('click', (event) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (target.closest('.btn-more')) telemetry.overflowClicks += 1
      if (target.closest('.view-details-link')) telemetry.detailClicks += 1
      if (target.closest('.expand-btn')) telemetry.expandClicks += 1
    }, true)

    const countMatches = (node: Node, selector: string) => {
      if (!(node instanceof Element)) return 0
      return Number(node.matches(selector)) + node.querySelectorAll(selector).length
    }
    new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          telemetry.menuOpenings += countMatches(node, '.actions-dropdown')
          telemetry.expansions += countMatches(node, '.stream-expanded')
          telemetry.ripples += countMatches(node, '.ripple-effect-element')
        }
      }
    }).observe(document, { childList: true, subtree: true })

    Object.defineProperty(Navigator.prototype, 'vibrate', {
      configurable: true,
      value: () => {
        telemetry.vibrations += 1
        return true
      },
    })
  })
}

async function resetActivationTelemetry(page: Page) {
  await page.evaluate(() => {
    const telemetry = (window as typeof window & { __gestureTelemetry: GestureTelemetry }).__gestureTelemetry
    telemetry.routeChanges = 0
    telemetry.menuOpenings = 0
    telemetry.expansions = 0
    telemetry.ripples = 0
    telemetry.vibrations = 0
    telemetry.overflowClicks = 0
    telemetry.detailClicks = 0
    telemetry.expandClicks = 0
  })
}

async function readTelemetry(page: Page) {
  return page.evaluate(
    () => (window as typeof window & { __gestureTelemetry: GestureTelemetry }).__gestureTelemetry,
  )
}

async function centerOf(locator: Locator) {
  await locator.scrollIntoViewIfNeeded()
  const box = await locator.boundingBox()
  if (!box) throw new Error('Gesture target has no bounding box')
  return {
    x: Math.round(box.x + box.width / 2),
    y: Math.round(box.y + box.height / 2),
  }
}

async function touchGesture(
  cdp: CDPSession,
  start: { x: number; y: number },
  end: { x: number; y: number },
  holdMs = 0,
) {
  await cdp.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ ...start, id: 1, radiusX: 4, radiusY: 4, force: 1 }],
  })
  if (holdMs > 0) await new Promise(resolve => setTimeout(resolve, holdMs))
  await cdp.send('Input.dispatchTouchEvent', {
    type: 'touchMove',
    touchPoints: [{ ...end, id: 1, radiusX: 4, radiusY: 4, force: 1 }],
  })
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
}

async function touchTap(cdp: CDPSession, locator: Locator) {
  const point = await centerOf(locator)
  await cdp.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ ...point, id: 1, radiusX: 4, radiusY: 4, force: 1 }],
  })
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
}

test.describe('mobile touch stability', () => {
  test.beforeEach(async ({ page, browserName }, testInfo) => {
    test.skip(browserName !== 'chromium' || testInfo.project.name !== 'mobile')
    await installGestureTelemetry(page)
  })

  test('100 vertical pans and 20 slow-start pans remain inert', async ({ page }) => {
    test.setTimeout(90_000)
    await page.goto('/streamers')
    const card = page.locator('.streamer-card-content').first()
    await expect(card).toBeVisible()
    await page.waitForTimeout(250)
    await resetActivationTelemetry(page)
    const cdp = await page.context().newCDPSession(page)

    for (let index = 0; index < 100; index += 1) {
      const start = await centerOf(card)
      const direction = index % 2 === 0 ? -1 : 1
      await touchGesture(cdp, start, { x: start.x, y: start.y + direction * 55 })
    }

    let telemetry = await readTelemetry(page)
    expect(telemetry).toMatchObject({
      routeChanges: 0,
      menuOpenings: 0,
      expansions: 0,
      ripples: 0,
      vibrations: 0,
      overflowClicks: 0,
      detailClicks: 0,
      expandClicks: 0,
      globalMainTouchListeners: { touchstart: 0, touchmove: 0, touchend: 0 },
    })

    for (let index = 0; index < 20; index += 1) {
      const start = await centerOf(card)
      await touchGesture(cdp, start, { x: start.x + 5, y: start.y - 55 }, 525)
    }

    telemetry = await readTelemetry(page)
    expect(telemetry.menuOpenings).toBe(0)
    expect(telemetry.vibrations).toBe(0)
    expect(telemetry.overflowClicks).toBe(0)
    expect(telemetry.detailClicks).toBe(0)
    await cdp.detach()
  })

  test('diagonal streamer and stream-history pans do not activate', async ({ page }) => {
    const cdp = await page.context().newCDPSession(page)
    await page.goto('/streamers')
    const streamerCard = page.locator('.streamer-card-content').first()
    await expect(streamerCard).toBeVisible()
    await resetActivationTelemetry(page)
    let start = await centerOf(streamerCard)
    await touchGesture(cdp, start, { x: start.x + 45, y: start.y - 70 })
    expect(await readTelemetry(page)).toMatchObject({
      routeChanges: 0,
      menuOpenings: 0,
      ripples: 0,
      overflowClicks: 0,
      detailClicks: 0,
    })

    await page.goto('/streamers/1')
    await page.getByRole('tab', { name: 'Videos' }).click()
    const streamRow = page.locator('.stream-compact').first()
    await expect(streamRow).toBeVisible()
    await resetActivationTelemetry(page)
    start = await centerOf(streamRow)
    await touchGesture(cdp, start, { x: start.x - 45, y: start.y - 70 })
    expect(await readTelemetry(page)).toMatchObject({
      routeChanges: 0,
      expansions: 0,
      ripples: 0,
      expandClicks: 0,
    })
    await expect(page.locator('.stream-expanded')).toHaveCount(0)
    await cdp.detach()
  })

  test('explicit touch taps activate each control exactly once', async ({ page }) => {
    const cdp = await page.context().newCDPSession(page)
    await page.goto('/streamers')
    const overflow = page.locator('.streamer-card .btn-more').first()
    await expect(overflow).toBeVisible()
    await expect(overflow).toHaveAccessibleName(/^Actions for /)
    const overflowSize = await overflow.evaluate(element => {
      const style = getComputedStyle(element)
      return { width: style.width, height: style.height }
    })
    expect(overflowSize).toEqual({ width: '48px', height: '48px' })
    await resetActivationTelemetry(page)

    await touchTap(cdp, overflow)
    await expect(overflow).toHaveAttribute('aria-expanded', 'true')
    expect(await readTelemetry(page)).toMatchObject({ menuOpenings: 1, overflowClicks: 1 })
    await touchTap(cdp, overflow)
    await expect(overflow).toHaveAttribute('aria-expanded', 'false')
    expect(await readTelemetry(page)).toMatchObject({ menuOpenings: 1, overflowClicks: 2 })

    const details = page.locator('.streamer-card .view-details-link').first()
    const detailsPath = await details.getAttribute('href')
    expect(detailsPath).toMatch(/^\/streamers\/\d+$/)
    await touchTap(cdp, details)
    await expect(page).toHaveURL(new RegExp(`${detailsPath}$`))
    expect(await readTelemetry(page)).toMatchObject({ routeChanges: 1, detailClicks: 1 })

    await page.getByRole('tab', { name: 'Videos' }).click()
    const expand = page.locator('.stream-card .expand-btn').first()
    await expect(expand).toHaveAccessibleName('Expand stream details')
    await expect(expand).toBeVisible()
    const expandBox = await expand.boundingBox()
    expect(expandBox?.width).toBeGreaterThanOrEqual(44)
    expect(expandBox?.height).toBeGreaterThanOrEqual(44)
    await resetActivationTelemetry(page)
    await expand.tap()
    expect((await readTelemetry(page)).expandClicks).toBe(1)
    await expect(expand).toHaveAttribute('aria-expanded', 'true')
    expect((await readTelemetry(page)).expansions).toBe(1)
    await cdp.detach()
  })

  test('keyboard route, menu, Enter, and Space activation occur once', async ({ page }) => {
    await page.goto('/streamers')
    const overflow = page.locator('.streamer-card .btn-more').first()
    await expect(overflow).toHaveAccessibleName(/^Actions for /)
    await overflow.focus()
    await resetActivationTelemetry(page)
    await overflow.press('Enter')
    await expect(overflow).toHaveAttribute('aria-expanded', 'true')
    expect(await readTelemetry(page)).toMatchObject({ menuOpenings: 1, overflowClicks: 1 })
    await overflow.press('Escape')
    await expect(overflow).toBeFocused()
    await expect(overflow).toHaveAttribute('aria-expanded', 'false')

    await overflow.press('Space')
    await expect(overflow).toHaveAttribute('aria-expanded', 'true')
    expect(await readTelemetry(page)).toMatchObject({ menuOpenings: 2, overflowClicks: 2 })
    await overflow.press('Escape')

    const details = page.locator('.streamer-card .view-details-link').first()
    const detailsPath = await details.getAttribute('href')
    expect(detailsPath).toMatch(/^\/streamers\/\d+$/)
    await details.focus()
    await resetActivationTelemetry(page)
    await details.press('Enter')
    await expect(page).toHaveURL(new RegExp(`${detailsPath}$`))
    expect(await readTelemetry(page)).toMatchObject({ routeChanges: 1, detailClicks: 1 })

    await page.getByRole('tab', { name: 'Videos' }).click()
    const expand = page.locator('.stream-card .expand-btn').first()
    await expect(expand).toHaveAccessibleName('Expand stream details')
    await resetActivationTelemetry(page)
    await expand.press('Enter')
    expect((await readTelemetry(page)).expandClicks).toBe(1)
    await expect(expand).toHaveAttribute('aria-expanded', 'true')
    expect((await readTelemetry(page)).expansions).toBe(1)
    await expand.press('Enter')
    await expect(expand).toHaveAttribute('aria-expanded', 'false')
    expect((await readTelemetry(page)).expansions).toBe(1)
    expect((await readTelemetry(page)).expandClicks).toBe(2)
    await expand.press('Space')
    await expect(expand).toHaveAttribute('aria-expanded', 'true')
    expect((await readTelemetry(page)).expansions).toBe(2)
    expect((await readTelemetry(page)).expandClicks).toBe(3)
  })

  test('streamer detail tabs retain horizontal touch scrolling', async ({ page }) => {
    await page.goto('/streamers/1')
    const tabs = page.getByRole('tablist', { name: 'Streamer detail sections' })
    await expect(tabs).toBeVisible()
    const dimensions = await tabs.evaluate(element => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      touchAction: getComputedStyle(element).touchAction,
    }))
    expect(dimensions.scrollWidth).toBeGreaterThan(dimensions.clientWidth)
    expect(dimensions.touchAction).not.toBe('pan-y')

    const cdp = await page.context().newCDPSession(page)
    const start = await centerOf(tabs)
    await touchGesture(cdp, { x: start.x + 120, y: start.y }, { x: start.x - 120, y: start.y })
    await expect.poll(() => tabs.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)
    await cdp.detach()
  })
})
