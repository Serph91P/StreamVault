import { expect, test } from '@playwright/test'

for (const width of [360, 1440]) {
  test(`recording auth status remains readable without priority UI at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')

    await expect(page.getByText('Authenticated Twitch recording', { exact: true })).toBeVisible()
    await expect(page.getByText('-25', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Priority', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Waiting for authenticated recording capacity.', { exact: true })).toBeVisible()
    await expect(page.getByText('A short segment-boundary gap may follow this auth handoff.', { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
      await page.evaluate(() => document.documentElement.clientWidth),
    )
  })
}
