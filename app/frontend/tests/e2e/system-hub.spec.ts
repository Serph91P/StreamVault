import { expect, test } from '@playwright/test'

for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 1440, height: 900 }]) {
  for (const theme of ['dark', 'light'] as const) {
    test(`renders opaque system navigation cards at ${theme} ${viewport.width}px without overflow`, async ({ page }, testInfo) => {
      await page.setViewportSize(viewport)
      await page.goto('/', { waitUntil: 'domcontentloaded' })
      await page.evaluate(selectedTheme => localStorage.setItem('streamvault-theme', selectedTheme), theme)
      await page.goto('/system', { waitUntil: 'domcontentloaded' })

      const cards = page.locator('.system-hub-card')
      await expect(cards).toHaveCount(3)
      await expect(cards.nth(0)).toHaveAttribute('href', '/settings')
      await expect(cards.nth(1)).toHaveAttribute('href', '/admin')
      await expect(cards.nth(2)).toHaveAttribute('href', '/subscriptions')
      await expect(cards.nth(0).locator('svg')).toHaveCSS('width', '24px')
      await expect(cards.nth(0)).toBeVisible()

      const styles = await cards.nth(0).evaluate(element => {
        const style = getComputedStyle(element)
        return {
          background: style.backgroundColor,
          border: style.borderTopWidth,
          backdropFilter: style.backdropFilter,
          minHeight: style.minHeight,
          boxShadow: style.boxShadow,
          transform: style.transform,
        }
      })
      expect(styles.background).not.toBe('rgba(0, 0, 0, 0)')
      expect(styles.border).toBe('1px')
      expect(styles.backdropFilter).toBe('none')
      expect(styles.minHeight).toBe('44px')
      expect(styles.boxShadow).toBe('none')
      expect(styles.transform).toBe('none')
      await cards.nth(0).hover()
      await expect(cards.nth(0)).toHaveCSS('box-shadow', 'none')
      await expect(cards.nth(0)).toHaveCSS('transform', 'none')
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)

      await cards.nth(0).focus()
      await expect(cards.nth(0)).toBeFocused()
      await cards.nth(2).evaluate(element => element.scrollIntoView({ block: 'end' }))
      const finalCard = await cards.nth(2).boundingBox()
      const bottomNavLocator = page.locator('.bottom-nav')
      const bottomNav = await bottomNavLocator.count() === 1 ? await bottomNavLocator.boundingBox() : null
      expect(finalCard?.y).toBeGreaterThanOrEqual(0)
      expect(finalCard && bottomNav ? finalCard.y + finalCard.height <= bottomNav.y : true, `final card ${JSON.stringify(finalCard)} must clear bottom navigation ${JSON.stringify(bottomNav)}`).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`system-hub-${theme}-${viewport.width}.png`), fullPage: true, animations: 'disabled' })
    })
  }
}
