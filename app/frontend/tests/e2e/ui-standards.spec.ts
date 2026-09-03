import { expect, test } from '@playwright/test'
import axe from 'axe-core'
import type { Page } from '@playwright/test'

type Theme = 'dark' | 'light'

interface AxeNode {
  target: string[]
}

interface AxeViolation {
  id: string
  nodes: AxeNode[]
}

const routes = [
  { path: '/', heading: 'Live Streamers' },
  { path: '/streamers', heading: 'Streamers' },
  { path: '/streamers/1', heading: 'Streamer Alpha' },
  { path: '/videos', heading: 'Videos' },
]

async function setTheme(page: Page, theme: Theme) {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
}

async function scanUiStandards(page: Page) {
  await page.addScriptTag({ content: axe.source })
  return page.evaluate(async () => {
    const browserAxe = (window as typeof window & {
      axe: {
        run: (
          context: Document,
          options: { runOnly: { type: 'rule'; values: string[] } },
        ) => Promise<{ violations: AxeViolation[] }>
      }
    }).axe

    return browserAxe.run(document, {
      runOnly: { type: 'rule', values: ['color-contrast', 'target-size'] },
    })
  })
}

function formatViolations(violations: AxeViolation[]) {
  return violations
    .map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`)
    .join('\n')
}

for (const theme of ['dark', 'light'] as const) {
  for (const route of routes) {
    test(`${theme} ${route.path} has no stable contrast, target-size, or console errors`, async ({ page }) => {
      const consoleErrors: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error') consoleErrors.push(message.text())
      })
      page.on('pageerror', (error) => consoleErrors.push(error.message))
      await setTheme(page, theme)

      await page.goto(route.path)
      await expect(page.getByRole('heading', { name: route.heading, exact: true })).toBeVisible()
      await page.waitForTimeout(400)

      const { violations } = await scanUiStandards(page)
      expect(violations, formatViolations(violations)).toEqual([])
      expect(consoleErrors).toEqual([])
    })
  }
}

test('canonical interaction tokens expose the product target contract', async ({ page }) => {
  await page.goto('/videos')
  const tokens = await page.evaluate(() => {
    const styles = getComputedStyle(document.documentElement)
    return {
      minimum: styles.getPropertyValue('--control-target-min').trim(),
      mobile: styles.getPropertyValue('--control-target-mobile').trim(),
      focusRing: styles.getPropertyValue('--focus-ring').trim(),
      gap: styles.getPropertyValue('--interactive-gap').trim(),
      rowDensity: styles.getPropertyValue('--row-density').trim(),
    }
  })

  expect(tokens).toMatchObject({
    minimum: '44px',
    mobile: '48px',
    gap: '8px',
    rowDensity: '56px',
  })
  expect(tokens.focusRing).toMatch(/^2px solid /)
})

test('reduced motion suppresses nonessential motion without disabling scrolling', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/streamers')
  await expect(page.getByRole('heading', { name: 'Streamers', exact: true })).toBeVisible()
  await expect(page.locator('.streamer-card.is-recording')).toBeVisible()
  await page.evaluate(() => {
    document.documentElement.style.scrollBehavior = 'smooth'
  })

  const motion = await page.evaluate(() => {
    const card = document.querySelector('.streamer-card.is-recording')
    if (!card) throw new Error('Expected a recording streamer card')
    const cardStyle = getComputedStyle(card, '::after')
    const bodyStyle = getComputedStyle(document.body)
    return {
      animationDuration: cardStyle.animationDuration,
      transitionDuration: bodyStyle.transitionDuration,
      scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
    }
  })

  expect(parseFloat(motion.animationDuration)).toBeLessThanOrEqual(0.001)
  expect(parseFloat(motion.transitionDuration)).toBeLessThanOrEqual(0.001)
  expect(motion.scrollBehavior).toBe('smooth')
})

test('active video filters are native keyboard-removable controls', async ({ page }) => {
  await page.goto('/videos')
  await expect(page.getByRole('heading', { name: 'Videos', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Filters' }).click()
  await page.getByLabel('Filter videos by streamer').selectOption({ index: 1 })
  await page.getByLabel('Filter videos by date').selectOption('week')
  await page.getByLabel('Filter videos by duration').selectOption('medium')

  const removableFilters = page.getByRole('button', { name: /^Remove .+ filter$/ })
  await expect(removableFilters).toHaveCount(3)
  await removableFilters.first().focus()
  await removableFilters.first().press('Enter')
  await expect(removableFilters).toHaveCount(2)
})
