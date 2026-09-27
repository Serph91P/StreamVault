import { expect, test, type Page } from '@playwright/test'
import axe from 'axe-core'

type Theme = 'dark' | 'light'

async function openStreamers(page: Page, theme: Theme) {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
  await page.goto('/streamers')
  await expect(page.getByRole('heading', { name: 'Streamers', exact: true })).toBeVisible()
}

for (const theme of ['dark', 'light'] as const) {
  test(`Streamers page header remains a solid accessible title in ${theme} theme`, async ({ page }) => {
    await openStreamers(page, theme)
    const heading = page.getByRole('heading', { name: 'Streamers', exact: true })

    await expect(heading).toHaveCSS('background-image', 'none')
    await expect(heading).not.toHaveCSS('color', 'rgba(0, 0, 0, 0)')

    await page.addScriptTag({ content: axe.source })
    const result = await heading.evaluate(async (node) => {
      const browserAxe = (window as typeof window & { axe: typeof axe }).axe
      return browserAxe.run(node, { runOnly: { type: 'rule', values: ['color-contrast'] } })
    })
    const colorContrastPass = result.passes.find((rule) => rule.id === 'color-contrast')
    const colorContrastViolations = result.violations.filter((violation) => violation.id === 'color-contrast')
    const colorContrastIncomplete = result.incomplete.filter((entry) => entry.id === 'color-contrast')
    const rawAxeTargetResult = {
      theme,
      viewport: await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight })),
      passRule: colorContrastPass,
      passTargets: colorContrastPass?.nodes.map((node) => node.target) ?? [],
      violationTargets: colorContrastViolations.flatMap((rule) => rule.nodes.map((node) => node.target)),
      incompleteTargets: colorContrastIncomplete.flatMap((rule) => rule.nodes.map((node) => node.target)),
    }
    console.log(`AXE_H1_TARGET ${JSON.stringify(rawAxeTargetResult)}`)

    expect(colorContrastPass).toBeDefined()
    expect(colorContrastPass?.nodes.some((node) => node.target.includes('h1'))).toBe(true)
    expect(colorContrastViolations).toEqual([])
    expect(colorContrastIncomplete).toEqual([])
  })
}

test('the unchanged Axe contrast rule still reports a visible poor-contrast control', async ({ page }) => {
  await page.setContent('<main style="background:#fff"><div id="poor-contrast-control" style="display:block;color:#ddd;background:#fff;font:16px Arial">VISIBLE CONTRAST CONTROL</div></main>')
  await page.addScriptTag({ content: axe.source })
  const result = await page.evaluate(async () => {
    const browserAxe = (window as typeof window & { axe: typeof axe }).axe
    return browserAxe.run(document, { runOnly: { type: 'rule', values: ['color-contrast'] } })
  })

  const seriousPoorContrastViolation = result.violations
    .filter((violation) => violation.id === 'color-contrast' && violation.impact === 'serious')
    .find((violation) => violation.nodes.some((node) => node.target.includes('#poor-contrast-control')))
  console.log(
    `AXE_NEGATIVE_CONTROL ${JSON.stringify({
      seriousTargets: seriousPoorContrastViolation?.nodes.map((node) => node.target) ?? [],
      impact: seriousPoorContrastViolation?.impact ?? null,
    })}`,
  )

  expect(seriousPoorContrastViolation).toBeDefined()
})
