import { expect, test, type Page } from '@playwright/test'

const viewports = [
  { width: 320, height: 568 },
  { width: 360, height: 640 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
] as const

async function assertButtonFitsViewport(page: Page, label: string) {
  const button = page.getByRole('button', { name: label })
  await expect(button).toBeVisible()
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
  // Mock mode intentionally has no media binary at the API stream URL. Keep its
  // native load error from covering the custom controls while this test checks
  // their independent layout and chapter interaction contract.
  await page.addInitScript(() => {
    document.addEventListener('error', (event) => {
      if (event.target instanceof HTMLVideoElement) event.stopImmediatePropagation()
    }, true)
  })

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.goto('/streamer/1/stream/1/watch?title=Synthetic%20recording&streamerName=alpha&origin=%2Fvideos%3Fq%3Dalpha%26streamer%3Dalpha%26sort%3Dtitle%26view%3Dlist&scroll=480', { waitUntil: 'domcontentloaded' })
    await expect(page.getByRole('heading', { name: 'Morning Talk Show - Community Discussion' })).toBeVisible()
    await page.locator('video.video-element').dispatchEvent('canplay')

    await assertButtonFitsViewport(page, 'Play')
    await assertButtonFitsViewport(page, 'Fullscreen')
    await assertButtonFitsViewport(page, 'Chapters')
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)

    await page.getByRole('button', { name: 'Chapters' }).click()
    const dialog = page.getByRole('dialog', { name: 'Chapters' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toBeFocused()
    const dialogBox = await dialog.boundingBox()
    expect(dialogBox!.width).toBeLessThanOrEqual(viewport.width)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)

    await page.screenshot({ path: testInfo.outputPath(`issue-828-player-${viewport.width}.png`) })

    await page.getByRole('button', { name: 'Back to previous page' }).click()
    await expect(page).toHaveURL(/\/videos\?q=alpha&streamer=alpha&sort=title&view=list$/)
  }
})
