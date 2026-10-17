import { expect, type Locator, type Page } from '@playwright/test'
import { localSeekMedia } from './media/issue828Media'
import { syntheticReply, type ChapterVariant } from './issue828SyntheticApi'
import { isMotionSettled } from './issue828Motion'

/** Wait for real Vue lifecycle, effective visibility and finite motion completion. */
export async function readyForSettledMotion(target: Locator) {
  await expect(target).toBeVisible()
  await expect.poll(() => target.evaluate(isMotionSettled)).toBe(true)
}

export async function installSyntheticApi(page: Page, variant: ChapterVariant) {
  const unexpected: string[] = []
  const requests: string[] = []
  let release!: () => void
  const chaptersReady = new Promise<void>(resolve => { release = resolve })
  const origin = 'http://127.0.0.1:4182'
  await page.route('**/*', async route => {
    const request = route.request()
    const url = new URL(request.url())
    if (url.origin !== origin) {
      unexpected.push(`External: ${url.origin}${url.pathname}`)
      return route.abort('blockedbyclient')
    }
    if (!/^\/(api|auth)\//.test(url.pathname) || request.isNavigationRequest()) return route.continue()
    requests.push(url.pathname)
    if (/^\/api\/videos\/\d+\/stream$/.test(url.pathname)) return localSeekMedia(route)
    if (/^\/api\/videos\/\d+\/chapters$/.test(url.pathname)) await chaptersReady
    const reply = syntheticReply(url.pathname + url.search, request.method(), variant)
    if (reply.status !== 200) unexpected.push(`${request.method()} ${url.pathname}: ${reply.status}`)
    return route.fulfill({ status: reply.status, json: reply.body })
  })
  // An isolated fixture has no live realtime service; do not let the app connect
  // to a provider or pretend a connected stream. REST remains genuine HTTP.
  await page.routeWebSocket(/.*/, socket => socket.close({ code: 1000, reason: 'Synthetic REST-only fixture' }))
  return { requests, unexpected, releaseChapters: release }
}

/** Physical scroll + hit-test readiness BEFORE measuring the click origin. */
export async function readyForMeasuredClick(page: Page, target: Locator) {
  await readyForSettledMotion(target)
  await target.evaluate(element => element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' }))
  await expect.poll(() => target.evaluate(element => {
    const box = element.getBoundingClientRect()
    const x = box.x + box.width / 2
    const y = box.y + box.height / 2
    return x >= 0 && y >= 0 && x < innerWidth && y < innerHeight && element.contains(document.elementFromPoint(x, y))
  })).toBe(true)
  await target.click({ trial: true })
  return page.evaluate(() => window.scrollY)
}

/** Observation only: install before the standard click, never change app state. */
export function observeOriginClick(element: Element | null) {
  if (!element) throw new Error('Origin click target is missing')
  const sample = {
    clicks: 0,
    trusted: false,
    scroll: null as number | null,
    cleanup: () => element.removeEventListener('click', capture, true),
  }
  function capture(event: Event) {
    sample.clicks++
    sample.trusted = event.isTrusted
    sample.scroll = element!.ownerDocument.defaultView?.scrollY ?? null
  }
  element.addEventListener('click', capture, { once: true, capture: true })
  return sample
}

export function requireOriginScroll(sample: { clicks: number; trusted: boolean; scroll: number | null }) {
  if (sample.clicks !== 1 || !sample.trusted || typeof sample.scroll !== 'number'
    || !Number.isFinite(sample.scroll) || sample.scroll <= 0) {
    throw new Error('Expected exactly one trusted origin click at a finite positive scroll')
  }
  return sample.scroll
}

/** Readiness must precede this one genuine navigation click. Handle stays owned. */
export async function clickAndMeasureOrigin(target: Locator): Promise<number> {
  const handle = await target.evaluateHandle(observeOriginClick)
  try {
    await target.click()
    return requireOriginScroll(await handle.evaluate(sample => ({
      clicks: sample.clicks, trusted: sample.trusted, scroll: sample.scroll,
    })))
  } finally {
    try { await handle.evaluate(sample => sample.cleanup()) }
    finally { await handle.dispose() }
  }
}
