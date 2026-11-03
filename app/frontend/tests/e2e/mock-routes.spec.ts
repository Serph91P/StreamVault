import { expect, test } from '@playwright/test'

const routes = [
  { path: '/', heading: 'Meine Kanäle' },
  { path: '/overview', heading: 'Live Streamers' },
  { path: '/activity', heading: 'Aktivität' },
  { path: '/streamers/manage', heading: 'Kanalverwaltung' },
  { path: '/streamers', heading: 'Meine Kanäle' },
  { path: '/streamers/1', heading: 'Streamer Alpha' },
  { path: '/videos', heading: 'Aufzeichnungen' },
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
