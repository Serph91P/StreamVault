import { expect, test, type Locator, type Page } from '@playwright/test'
import { localSeekMedia } from '../fixtures/media/issue828Media'

async function focusByTab(page: Page, target: Locator) {
  for (let presses = 0; presses < 100; presses++) {
    await page.keyboard.press('Tab')
    if (await target.evaluate(element => element === document.activeElement)) return
  }
  throw new Error('Overview VideoCard link was not reached through native Tab navigation')
}

test('issue 828 keeps native VideoCard keyboard navigation and the Overview return path', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/videos/*/stream', localSeekMedia)

  await page.goto('/overview', { waitUntil: 'domcontentloaded' })
  const overviewUrl = page.url()
  const videoLink = page.locator('.dashboard-video-grid .video-card-link').first()
  await expect(videoLink).toBeVisible()

  await focusByTab(page, videoLink)
  await expect(videoLink).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/streamer\/1\/stream\/1\/watch(?:\?|$)/)

  await page.getByRole('button', { name: 'Back to previous page' }).click()
  await expect(page).toHaveURL(overviewUrl)
})
