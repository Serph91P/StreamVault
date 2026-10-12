import { writeFile } from 'node:fs/promises'
import { expect, test, type Page } from '@playwright/test'
import axe from 'axe-core'

type Theme = 'dark' | 'light'

// This rendering-only contrast suite must observe authored CSS, not a stale
// service-worker response. PWA behavior is covered by its dedicated suite.
test.use({ serviceWorkers: 'block' })

function relativeLuminance([red, green, blue]: number[]) {
  const channels = [red, green, blue].map(channel => channel / 255).map(channel => (
    channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  ))
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function contrastRatio(foreground: number[], background: number[]) {
  const [lighter, darker] = [relativeLuminance(foreground), relativeLuminance(background)].sort((a, b) => b - a)
  return (lighter + 0.05) / (darker + 0.05)
}

function parseRgb(value: string) {
  const match = value.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)$/)
  if (!match) throw new Error(`Expected rgb() or rgba(), received ${value}`)
  return { channels: match.slice(1, 4).map(Number), alpha: Number(match[4] ?? 1) }
}

function composite(foreground: ReturnType<typeof parseRgb>, background: number[]) {
  return foreground.channels.map((channel, index) => Math.round(channel * foreground.alpha + background[index] * (1 - foreground.alpha)))
}

async function openStreamers(page: Page, theme: Theme) {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
  await page.goto('/streamers')
  await expect(page.getByRole('heading', { name: 'Streamers', exact: true })).toBeVisible()
}

for (const theme of ['dark', 'light'] as const) {
  test(`active streamer filter badge passes contrast in ${theme} theme`, async ({ page }, testInfo) => {
    await openStreamers(page, theme)
    const badge = page.locator('.active.filter-tab > .tab-badge').first()
    await expect(badge).toBeVisible()
    await page.addScriptTag({ content: axe.source })

    const result = await badge.evaluate(async (node) => {
      const browserAxe = (window as typeof window & { axe: typeof axe }).axe
      const axeResult = await browserAxe.run(node, { runOnly: { type: 'rule', values: ['color-contrast'] } })
      const style = getComputedStyle(node)
      return {
        axe: axeResult,
        foreground: style.color,
        background: style.backgroundColor,
        parentBackground: getComputedStyle(node.parentElement!).backgroundColor,
        selector: '.active.filter-tab > .tab-badge',
        viewport: { width: window.innerWidth, height: window.innerHeight },
      }
    })
    await page.screenshot({ path: testInfo.outputPath(`streamers-filter-badge-${theme}.png`), fullPage: true })

    const colorContrastPass = result.axe.passes.find(rule => rule.id === 'color-contrast')
    const colorContrastViolations = result.axe.violations.filter(rule => rule.id === 'color-contrast')
    const colorContrastIncomplete = result.axe.incomplete.filter(rule => rule.id === 'color-contrast')
    const passTargets = colorContrastPass?.nodes.flatMap(node => node.target) ?? []
    const incompleteTargets = colorContrastIncomplete.flatMap(rule => rule.nodes.flatMap(node => node.target))
    const violationTargets = colorContrastViolations.flatMap(rule => rule.nodes.flatMap(node => node.target))
    const background = parseRgb(result.background)
    const compositeBackground = composite(background, parseRgb(result.parentBackground).channels)
    const ratio = contrastRatio(parseRgb(result.foreground).channels, compositeBackground)
    const evidence = {
      theme,
      project: testInfo.project.name,
      ...result,
      passTargets,
      incompleteTargets,
      violationTargets,
      ratio,
      compositeBackground,
    }
    console.log(`AXE_ACTIVE_FILTER_BADGE ${JSON.stringify(evidence)}`)
    const rawAxePath = testInfo.outputPath(`raw-axe-active-filter-badge-${theme}-${testInfo.project.name}.json`)
    await writeFile(rawAxePath, `${JSON.stringify(evidence, null, 2)}\n`)
    await testInfo.attach(`axe-active-filter-badge-${theme}-${testInfo.project.name}.json`, {
      path: rawAxePath,
      contentType: 'application/json',
    })

    expect(colorContrastPass).toBeDefined()
    expect(passTargets).toContain('.active.filter-tab > .tab-badge')
    expect(result.background).toMatch(/^rgb\(/)
    expect(violationTargets).toEqual([])
    expect(incompleteTargets).toEqual([])
    expect(ratio).toBeGreaterThanOrEqual(4.5)
  })

  test(`Streamers heading retains its exact color-contrast pass in ${theme} theme`, async ({ page }) => {
    await openStreamers(page, theme)
    const heading = page.getByRole('heading', { name: 'Streamers', exact: true })
    await page.addScriptTag({ content: axe.source })
    const result = await heading.evaluate(async (node) => (
      (window as typeof window & { axe: typeof axe }).axe.run(node, {
        runOnly: { type: 'rule', values: ['color-contrast'] },
      })
    ))
    const pass = result.passes.find(rule => rule.id === 'color-contrast')
    const targets = pass?.nodes.flatMap(node => node.target) ?? []

    expect(pass).toBeDefined()
    expect(targets).toContain('h1')
    expect(result.violations.filter(rule => rule.id === 'color-contrast')).toEqual([])
    expect(result.incomplete.filter(rule => rule.id === 'color-contrast')).toEqual([])
  })

  test(`streamer VOD metadata passes contrast on subtle cards in ${theme} theme`, async ({ page }, testInfo) => {
    await openStreamers(page, theme)
    const vodLabels = page.locator('.streamer-stats > .stat-vods > span')
    await expect(vodLabels.first()).toBeVisible()
    await page.addScriptTag({ content: axe.source })

    const axeResult = await page.evaluate(async () => (
      (window as typeof window & { axe: typeof axe }).axe.run(document, {
        runOnly: { type: 'rule', values: ['color-contrast'] },
      })
    ))
    const evidence = await vodLabels.evaluateAll((nodes) => nodes.map((node) => {
      const card = node.closest('.surface-card')
      if (!card) throw new Error('VOD metadata must remain inside its semantic card surface')
      return {
        label: node.textContent?.trim(),
        foreground: getComputedStyle(node).color,
        background: getComputedStyle(card).backgroundColor,
      }
    }))

    const ratios = evidence.map(({ foreground, background }) => (
      contrastRatio(parseRgb(foreground).channels, parseRgb(background).channels)
    ))
    const violations = axeResult.violations.filter(rule => rule.id === 'color-contrast')
    const incomplete = axeResult.incomplete.filter(rule => rule.id === 'color-contrast')
    console.log(`AXE_STREAMER_VOD_METADATA ${JSON.stringify({ theme, project: testInfo.project.name, evidence, ratios, violations, incomplete })}`)

    expect(evidence.length).toBeGreaterThan(0)
    expect(violations).toEqual([])
    expect(incomplete).toEqual([])
    expect(Math.min(...ratios)).toBeGreaterThanOrEqual(4.5)
  })
}

test('negative control reports a serious color-contrast violation', async ({ page }) => {
  await page.setContent('<span id="contrast-negative-control" style="color: #777; background: #fff; font-size: 12px">Unreadable</span>')
  await page.addScriptTag({ content: axe.source })
  const result = await page.locator('#contrast-negative-control').evaluate(async (node) => (
    (window as typeof window & { axe: typeof axe }).axe.run(node, {
      runOnly: { type: 'rule', values: ['color-contrast'] },
    })
  ))
  const violation = result.violations.find(rule => rule.id === 'color-contrast')

  expect(violation).toBeDefined()
  expect(violation?.impact).toBe('serious')
  expect(violation?.nodes.flatMap(node => node.target)).toContain('#contrast-negative-control')
})
