import { expect, test } from '@playwright/test'
import axe from 'axe-core'

// Deterministic UI contract test, not a live-backend or Twitch acceptance test.
test.use({
  serviceWorkers: 'block',
  launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH },
})

for (const theme of ['light', 'dark']) {
  for (const width of [320, 390, 1024, 1440]) {
    test(`channel-first navigation and retained controls ${theme} ${width}`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 })
      await page.addInitScript(selectedTheme => localStorage.setItem('streamvault-theme', selectedTheme), theme)
      await page.route('**/auth/setup', route => route.fulfill({ json: { setup_required: false, welcome_completed: true } }))
      await page.route('**/api/twitch/connection-status', route => route.fulfill({ json: { connected: false } }))
      await page.goto('/')
      await expect(page.getByRole('heading', { name: 'Meine Kanäle', exact: true })).toBeVisible()
      await expect(page.locator('.streamer-card').first()).toBeVisible()
      await expect(page.getByRole('link', { name: 'Kanal hinzufügen', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Follows importieren', exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Kanäle verwalten', exact: true })).toBeVisible()
      const navigation = page.locator(width < 1024 ? '.bottom-nav' : '.sidebar-nav-list')
      await expect(navigation.getByRole('link', { name: 'Kanäle', exact: true })).toHaveAttribute('aria-current', 'page')
      await expect(navigation.getByRole('link')).toHaveCount(5)
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1)
      await page.addScriptTag({ content: axe.source })
      const contrast = await page.evaluate(async () => (await (window as unknown as { axe: typeof axe }).axe.run(document, { runOnly: ['color-contrast'] })).violations)
      expect(contrast.map(issue => ({ id: issue.id, nodes: issue.nodes.map(node => node.target) }))).toEqual([])
      await page.screenshot({ path: testInfo.outputPath(`channels-${theme}-${width}.png`), fullPage: true })

      await page.getByRole('textbox', { name: 'Kanäle suchen' }).fill('a-channel-that-does-not-exist')
      await expect(page.getByText('Keine passenden Kanäle', { exact: true })).toBeVisible()
      await page.getByRole('button', { name: 'Alle Kanäle anzeigen' }).click()
      await expect(page.locator('.streamer-card').first()).toBeVisible()

      await navigation.getByRole('link', { name: 'Aktivität', exact: true }).click()
      await expect(page.getByRole('heading', { name: 'Aktivität', exact: true })).toBeVisible()
      await page.getByRole('link', { name: 'Benachrichtigungsverlauf', exact: true }).click()
      await expect(page.locator('.notification-feed')).toBeVisible()
      await page.getByRole('link', { name: 'Gesamtübersicht', exact: true }).click()
      await expect(page.locator('.home-view')).toBeVisible()
      await page.getByRole('link', { name: 'StreamVault - Meine Kanäle', exact: true }).click()
      await expect(page.locator('.streamers-view')).toBeVisible()
    })
  }
}
