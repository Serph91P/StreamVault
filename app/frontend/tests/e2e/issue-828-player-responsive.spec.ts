import { expect, test, type Page } from '@playwright/test'
import { localSeekMedia } from '../fixtures/media/issue828Media'
import { readyForMeasuredClick, readyForSettledMotion } from '../fixtures/issue828Browser'

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 640 },
  { width: 390, height: 844 },
  { width: 568, height: 320 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
] as const

async function assertButtonFitsViewport(page: Page, label: string) {
  const button = page.getByRole('button', { name: label })
  await expect(button).toBeVisible()
  await readyForSettledMotion(button)
  const box = await button.boundingBox()
  expect(box, `${label} has a visible box`).not.toBeNull()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.y).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height)
  expect(box!.width).toBeGreaterThanOrEqual(43.9)
  expect(box!.height).toBeGreaterThanOrEqual(43.9)
}

test('issue 828 player keeps controls bounded and restores its in-app library origin', async ({ page }, testInfo) => {
  test.setTimeout(90_000)
  // Serve genuine, local synthetic H264 media. Do not suppress native errors or
  // dispatch canplay: decoding and a completed seek are part of this regression.
  await page.route('**/api/videos/*/stream', localSeekMedia)

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    // Enter through the real Library: origin/scroll are captured by VideoCard,
    // not fabricated by legacy player query parameters or injected history state.
    await page.goto('/videos?q=alpha&streamer=streamer_alpha&sort=title&view=list', { waitUntil: 'domcontentloaded' })
    const card = page.locator('.videos-container .video-card-link').last()
    await expect(card).toBeVisible()
    const originScroll = await readyForMeasuredClick(page, card)
    expect(originScroll).toBeGreaterThan(0)
    await card.click()
    await expect(page).toHaveURL(/\/streamer\/\d+\/stream\/\d+\/watch(?:\?|$)/)
    await expect(page.locator('video.video-element')).toBeAttached()
    const video = page.locator('video.video-element')
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).readyState)).toBeGreaterThanOrEqual(2)
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).duration)).toBe(12)

    await assertButtonFitsViewport(page, 'Play')
    await assertButtonFitsViewport(page, 'Fullscreen')
    await assertButtonFitsViewport(page, 'Chapters')
    await assertButtonFitsViewport(page, 'Mute')
    await assertButtonFitsViewport(page, 'Back to previous page')
    await expect(page.locator('.time-display')).toBeVisible()
    await expect(page.getByRole('slider', { name: 'Video progress' })).toBeVisible()
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)

    await page.getByRole('button', { name: 'Chapters' }).click()
    const dialog = page.getByRole('dialog', { name: 'Chapters' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toBeFocused()
    await readyForSettledMotion(dialog)
    const dialogBox = await dialog.boundingBox()
    expect(dialogBox!.width).toBeLessThanOrEqual(viewport.width)
    expect(dialogBox!.x).toBeGreaterThanOrEqual(0)
    expect(dialogBox!.y).toBeGreaterThanOrEqual(0)
    expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(viewport.height)
    expect(await dialog.evaluate(element => {
      const box = element.getBoundingClientRect()
      return element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2))
    })).toBe(true)
    await expect(dialog.locator('.chapter-item')).toHaveCount(1)
    expect(dialogBox!.height, 'one chapter stays compact').toBeLessThan(250)
    await expect(page.getByRole('dialog')).toHaveCount(1)
    const firstControl = dialog.getByRole('button', { name: 'Close chapters', exact: true })
    const lastControl = dialog.locator('.chapter-item').last()
    await page.keyboard.press('Tab')
    await expect(firstControl).toBeFocused()
    await page.keyboard.press('Shift+Tab')
    await expect(lastControl).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(firstControl).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Chapters', exact: true })).toBeFocused()

    // Establish a real nonzero decoded position, then use the actual chapter
    // button to seek back to the numeric default/start chapter at zero.
    await video.evaluate(element => { (element as HTMLVideoElement).currentTime = 6 })
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).seeking)).toBe(false)
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime)).toBe(6)
    await page.getByRole('button', { name: 'Chapters', exact: true }).click()
    await dialog.locator('.chapter-item').click()
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).currentTime)).toBe(0)
    await expect.poll(() => video.evaluate(element => (element as HTMLVideoElement).seeking)).toBe(false)
    expect(await video.evaluate(element => (element as HTMLVideoElement).error)).toBeNull()
    await dialog.getByRole('button', { name: 'Close chapters', exact: true }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Chapters', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Chapters', exact: true }).click()
    await expect(dialog).toBeVisible()
    await readyForSettledMotion(dialog)
    const outsideBox = await dialog.boundingBox()
    const outside = { x: outsideBox!.x - 2, y: outsideBox!.y - 2 }
    expect(outside.x).toBeGreaterThanOrEqual(0)
    expect(outside.y).toBeGreaterThanOrEqual(0)
    await page.mouse.click(outside.x, outside.y)
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Chapters', exact: true })).toBeFocused()

    await page.getByRole('button', { name: 'Fullscreen', exact: true }).click()
    await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true)
    await page.getByRole('button', { name: 'Chapters', exact: true }).click()
    await expect(dialog).toBeVisible()
    await readyForSettledMotion(dialog)
    expect(await dialog.evaluate(element => {
      const box = element.getBoundingClientRect()
      return element.contains(document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2))
    })).toBe(true)
    await dialog.locator('.chapter-item').click()
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Chapters', exact: true })).toBeFocused()
    await page.getByRole('button', { name: 'Exit Fullscreen', exact: true }).click()
    await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false)

    await page.screenshot({ path: testInfo.outputPath(`issue-828-player-${viewport.width}.png`) })

    await page.getByRole('button', { name: 'Back to previous page' }).click()
    await expect.poll(() => page.evaluate(() => {
      const url = new URL(location.href)
      return [url.pathname, ...['q', 'streamer', 'sort', 'view'].map(key => url.searchParams.get(key))]
    })).toEqual(['/videos', 'alpha', 'streamer_alpha', 'title', 'list'])
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(originScroll)
    await expect(page.getByPlaceholder('Search videos by title or streamer...')).toHaveValue('alpha')
    await expect(page.getByRole('combobox', { name: 'Sort videos', exact: true })).toHaveValue('title')
  }
})
