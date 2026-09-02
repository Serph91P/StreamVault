import { expect, test } from '@playwright/test'

const routes = [
  { path: '/', heading: 'Live Streamers' },
  { path: '/streamers', heading: 'Streamers' },
  { path: '/streamers/1', heading: 'Streamer Alpha' },
  { path: '/videos', heading: 'Videos' },
]

for (const route of routes) {
  test(`${route.path} renders without horizontal overflow`, async ({ page }) => {
    await page.goto(route.path)
    await expect(page.getByRole('heading', { name: route.heading, exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
      await page.evaluate(() => document.documentElement.clientWidth),
    )
  })
}
