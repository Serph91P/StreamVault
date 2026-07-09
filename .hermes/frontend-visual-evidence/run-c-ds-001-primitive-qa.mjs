import fs from 'node:fs/promises'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(path.join(process.cwd(), 'package.json'))
const { chromium } = require('playwright')
const axe = require('axe-core')

const baseURL = process.env.QA_BASE_URL || 'http://127.0.0.1:5173'
const outDir = path.resolve(process.env.QA_OUT_DIR || '../../.hermes/frontend-visual-evidence')
const qaRunLabel = process.env.QA_RUN_LABEL || 'dev server'
const commandOutputArtifact = process.env.QA_COMMAND_OUTPUT_ARTIFACT || '.hermes/frontend-visual-evidence/c-ds-001p-command-output.txt'
const overlaySelectors = ['.panel-entry-btn']
const themes = ['dark', 'light']
const widths = [390, 430, 768, 1440]

const scenarios = [
  {
    id: 'dashboard',
    path: '/',
    coverage: ['tokens', 'buttons', 'cards', 'status badges', 'loading states'],
  },
  {
    id: 'notification-dialog',
    path: '/',
    coverage: ['sheet/dialog surface', 'buttons', 'empty/error/loading states', 'focus states'],
    action: async (page) => {
      await page.getByRole('button', { name: /notifications/i }).first().click({ timeout: 5000 })
      await page.locator('[role="dialog"]').first().waitFor({ timeout: 5000 })
    },
  },
  {
    id: 'streamer-cards',
    path: '/streamers',
    coverage: ['cards', 'status badges', 'buttons', 'responsive grids'],
  },
  {
    id: 'library-cards',
    path: '/videos',
    coverage: ['cards', 'forms', 'buttons', 'status badges'],
  },
  {
    id: 'library-empty-state',
    path: '/videos',
    coverage: ['empty state', 'forms', 'buttons'],
    action: async (page) => {
      const search = page.locator('input[placeholder*="Search videos"]').first()
      await search.fill('qa-no-results-c-ds-001')
      await page.waitForTimeout(300)
    },
  },
  {
    id: 'library-delete-modal',
    path: '/videos',
    coverage: ['modal surface', 'buttons', 'disabled states', 'focus states'],
    action: async (page) => {
      await page.getByRole('button', { name: /^select$/i }).first().click({ timeout: 5000 })
      await page.locator('input[type="checkbox"]').first().check({ timeout: 5000, force: true })
      await page.getByRole('button', { name: /delete \(1\)/i }).first().click({ timeout: 5000 })
      await page.locator('[role="dialog"]').first().waitFor({ timeout: 5000 })
    },
  },
  {
    id: 'settings-notifications-form',
    path: '/settings',
    coverage: ['forms', 'buttons', 'disabled states', 'tables', 'cards'],
    action: async (page) => {
      await chooseSettingsSection(page, 'notifications')
    },
  },
  {
    id: 'settings-proxy-modal',
    path: '/settings',
    coverage: ['forms', 'modal surface', 'buttons', 'cards', 'error states'],
    action: async (page) => {
      await chooseSettingsSection(page, 'proxy')
      await page.getByRole('button', { name: /add proxy/i }).first().click({ timeout: 5000 })
      await page.locator('[role="dialog"]').first().waitFor({ timeout: 5000 })
    },
  },
]

async function chooseSettingsSection(page, value) {
  await page.waitForSelector('.settings-view', { timeout: 10000 })
  const labels = {
    notifications: 'Notifications',
    proxy: 'Proxy Management',
  }
  const label = labels[value] || value
  const select = page.locator('select.section-select').first()
  if (await select.count()) {
    await select.selectOption(value).catch(async () => {
      await page.locator('.settings-nav .nav-item').filter({ hasText: label }).first().click({ timeout: 5000 })
    })
  } else {
    await page.locator('.settings-nav .nav-item').filter({ hasText: label }).first().click({ timeout: 5000 })
  }
  await page.locator('.settings-content .section-title').filter({ hasText: label }).first().waitFor({ state: 'attached', timeout: 5000 })
  await page.waitForTimeout(500)
}

async function waitForApp(page) {
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => null)
  await page.locator('#app').waitFor({ timeout: 20000 })
  await page.waitForTimeout(450)
}

async function inspectPage(page) {
  return await page.evaluate(() => {
    const doc = document.documentElement
    const body = document.body
    const selectors = {
      buttons: 'button, .btn, .btn-action, .glass-btn-icon',
      disabledButtons: 'button:disabled, [aria-disabled="true"]',
      cards: '.glass-card, .surface-card, .streamer-card, .video-card, .status-card, [class*="card"]',
      badges: '.status-badge, .badge, [class*="badge"]',
      forms: 'input, select, textarea, .form-group, .input-field',
      dialogs: '[role="dialog"], .modal, .glass-popup-panel, .base-sheet',
      emptyStates: '.empty-state, [role="status"], [role="alert"]',
      skeletons: '.loading-skeleton, [class*="skeleton"], .loader',
      devtoolsPanelEntryButtons: '.panel-entry-btn',
    }
    const counts = Object.fromEntries(
      Object.entries(selectors).map(([key, selector]) => [key, document.querySelectorAll(selector).length]),
    )
    const focusable = Array.from(document.querySelectorAll('button, a[href], input, select, textarea, [tabindex]:not([tabindex="-1"])'))
    const text = body.innerText.replace(/\s+/g, ' ').trim()
    const cssVars = ['--background-color', '--background-dark', '--text-primary', '--text-secondary', '--primary-color', '--border-color']
    const styles = getComputedStyle(doc)
    return {
      title: document.title,
      path: location.pathname,
      dataTheme: doc.getAttribute('data-theme') || 'dark-default',
      horizontalOverflow: doc.scrollWidth > doc.clientWidth + 1,
      viewportWidth: doc.clientWidth,
      scrollWidth: doc.scrollWidth,
      bodyTextStart: text.slice(0, 220),
      counts,
      focusableCount: focusable.length,
      tokenSamples: Object.fromEntries(cssVars.map((key) => [key, styles.getPropertyValue(key).trim()])),
    }
  })
}

async function inspectFocus(page) {
  await page.keyboard.press('Tab')
  await page.waitForTimeout(60)
  return await page.evaluate(() => {
    const el = document.activeElement
    if (!el || el === document.body) return { moved: false }
    const style = getComputedStyle(el)
    return {
      moved: true,
      tag: el.tagName,
      text: (el.textContent || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 120),
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
      boxShadow: style.boxShadow,
    }
  })
}

async function runAxe(page) {
  await page.addScriptTag({ content: axe.source })
  const result = await page.evaluate(async () => window.axe.run(document, { resultTypes: ['violations'] }))
  return result.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    nodes: v.nodes.length,
    targets: v.nodes.slice(0, 5).map((n) => n.target.join(' ')),
  }))
}

function summarizeViolations(rows) {
  return summarizeViolationList(rows.flatMap((row) => row.axeViolations || []))
}

function isOverlayViolation(violation) {
  return (violation.targets || []).some((target) => overlaySelectors.some((selector) => target.includes(selector)))
}

function appViolations(row) {
  return (row.axeViolations || []).filter((violation) => !isOverlayViolation(violation))
}

function overlayViolations(row) {
  return (row.axeViolations || []).filter(isOverlayViolation)
}

function countViolationNodes(violations) {
  return violations.reduce((sum, violation) => sum + violation.nodes, 0)
}

function summarizeViolationList(violations) {
  const counts = new Map()
  for (const violation of violations) counts.set(violation.id, (counts.get(violation.id) || 0) + violation.nodes)
  return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]).map(([id, nodes]) => ({ id, nodes }))
}

function coverageRows(rows) {
  return themes.flatMap((theme) => widths.map((width) => {
    const scoped = rows.filter((row) => row.theme === theme && row.width === width)
    return {
      theme,
      width,
      scenarios: scoped.length,
      passed: scoped.filter((row) => row.ok).length,
      overflow: scoped.filter((row) => row.inspect?.horizontalOverflow).map((row) => row.scenario),
      axeViolations: scoped.reduce((sum, row) => sum + countViolationNodes(appViolations(row)), 0),
      overlayAxeViolations: scoped.reduce((sum, row) => sum + countViolationNodes(overlayViolations(row)), 0),
    }
  }))
}

async function writeMarkdown(result) {
  const lines = []
  lines.push('# C-DS-001 primitive visual QA matrix')
  lines.push('')
  lines.push(`Date: ${result.generatedAt}`)
  lines.push(`Base URL: ${result.baseURL}`)
  lines.push(`QA run label: ${result.qaRunLabel}`)
  lines.push(`Scope: ${result.themes.join(', ')} themes at ${result.widths.join(', ')} px.`)
  lines.push('')
  lines.push('## Result')
  lines.push('')
  lines.push(result.blocked ? 'Blocked. Local visual QA completed, but the design-system primitive gate cannot be signed off because accessibility and focus regressions remain.' : 'Passed. Local visual QA completed without blocking regressions.')
  lines.push('')
  lines.push('## Theme and breakpoint coverage')
  lines.push('')
  lines.push('| Theme | Width | Scenarios passed | Horizontal overflow | App axe nodes | Overlay axe nodes |')
  lines.push('| --- | ---: | ---: | --- | ---: | ---: |')
  for (const row of result.coverage) {
    lines.push(`| ${row.theme} | ${row.width} | ${row.passed}/${row.scenarios} | ${row.overflow.length ? row.overflow.join(', ') : 'none'} | ${row.axeViolations} | ${row.overlayAxeViolations} |`)
  }
  lines.push('')
  lines.push('## Primitive coverage')
  lines.push('')
  lines.push('| Primitive area | Scenario evidence |')
  lines.push('| --- | --- |')
  for (const [primitive, scenarioIds] of Object.entries(result.primitiveCoverage)) {
    lines.push(`| ${primitive} | ${scenarioIds.join(', ')} |`)
  }
  lines.push('')
  lines.push('## Observed regressions and WCAG concerns')
  lines.push('')
  if (result.regressions.length === 0) {
    lines.push('- No blocking visual regressions were detected by the automated matrix.')
  } else {
    for (const regression of result.regressions) lines.push(`- ${regression}`)
  }
  lines.push('')
  lines.push('## Axe summary')
  lines.push('')
  lines.push('### App DOM')
  lines.push('')
  lines.push('| Rule | Nodes |')
  lines.push('| --- | ---: |')
  if (result.appAxeSummary.length === 0) lines.push('| none | 0 |')
  for (const row of result.appAxeSummary) lines.push(`| ${row.id} | ${row.nodes} |`)
  lines.push('')
  lines.push('### Devtools overlay DOM')
  lines.push('')
  lines.push('| Rule | Nodes |')
  lines.push('| --- | ---: |')
  if (result.overlayAxeSummary.length === 0) lines.push('| none | 0 |')
  for (const row of result.overlayAxeSummary) lines.push(`| ${row.id} | ${row.nodes} |`)
  lines.push('')
  lines.push('## Devtools overlay isolation')
  lines.push('')
  lines.push(`- Overlay selectors excluded from app classification: ${result.overlaySelectors.join(', ')}`)
  lines.push(`- Captures with .panel-entry-btn in the DOM: ${result.overlayTargetSummary.rowsWithPanelEntryButton}/${result.rows.length}`)
  lines.push(`- App axe nodes after overlay target classification: ${result.appAxeNodeCount}`)
  lines.push(`- Overlay axe nodes: ${result.overlayAxeNodeCount}`)
  lines.push(`- Verdict: ${result.overlayIsolationVerdict}`)
  lines.push(`- Command output artifact: ${result.commandOutputArtifact}`)
  lines.push('')
  lines.push('## Unverified coverage')
  lines.push('')
  for (const item of result.unverified) lines.push(`- ${item}`)
  lines.push('')
  lines.push('## Evidence files')
  lines.push('')
  lines.push('- Raw JSON: `.hermes/frontend-visual-evidence/c-ds-001-primitive-qa-results.json`')
  lines.push('- QA script: `.hermes/frontend-visual-evidence/run-c-ds-001-primitive-qa.mjs`')
  lines.push(`- Screenshots captured: ${result.screenshots.length}`)
  lines.push('')
  await fs.writeFile(path.join(outDir, 'c-ds-001-primitive-qa-matrix.md'), lines.join('\n'))
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const rows = []
  const screenshots = []

  for (const theme of themes) {
    for (const width of widths) {
      const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1 })
      await context.addInitScript((selectedTheme) => {
        localStorage.setItem('streamvault-theme', selectedTheme)
      }, theme)
      const page = await context.newPage()
      for (const scenario of scenarios) {
        const row = { theme, width, scenario: scenario.id, path: scenario.path, coverage: scenario.coverage, ok: false }
        try {
          await page.goto(baseURL + scenario.path, { waitUntil: 'domcontentloaded' })
          await waitForApp(page)
          if (scenario.action) {
            await scenario.action(page)
            await page.waitForTimeout(350)
          }
          row.inspect = await inspectPage(page)
          row.focus = await inspectFocus(page)
          row.axeViolations = await runAxe(page)
          const file = `${theme}-${String(width).padStart(4, '0')}-${scenario.id}.png`
          await page.screenshot({ path: path.join(outDir, file), fullPage: true })
          row.screenshot = file
          screenshots.push(file)
          row.ok = true
        } catch (error) {
          row.error = String(error?.message || error)
        }
        rows.push(row)
      }
      await context.close()
    }
  }

  await browser.close()

  const primitiveCoverage = {}
  for (const scenario of scenarios) {
    for (const primitive of scenario.coverage) {
      primitiveCoverage[primitive] ||= []
      primitiveCoverage[primitive].push(scenario.id)
    }
  }

  const regressions = []
  const failedRows = rows.filter((row) => !row.ok)
  if (failedRows.length) regressions.push(`${failedRows.length} scenario captures failed: ${failedRows.map((row) => `${row.theme}/${row.width}/${row.scenario}`).join(', ')}.`)
  const overflowRows = rows.filter((row) => row.inspect?.horizontalOverflow)
  if (overflowRows.length) regressions.push(`Horizontal overflow detected in ${overflowRows.map((row) => `${row.theme}/${row.width}/${row.scenario}`).join(', ')}.`)
  const focusRows = rows.filter((row) => row.ok && !row.focus?.moved)
  if (focusRows.length) regressions.push(`Keyboard focus did not move after Tab in ${focusRows.map((row) => `${row.theme}/${row.width}/${row.scenario}`).join(', ')}.`)
  const colorContrastRows = rows.filter((row) => appViolations(row).some((v) => v.id === 'color-contrast'))
  if (colorContrastRows.length) regressions.push(`WCAG color contrast violations remain in ${colorContrastRows.length} scenario captures, including ${colorContrastRows.slice(0, 8).map((row) => `${row.theme}/${row.width}/${row.scenario}`).join(', ')}.`)
  const dialogRows = rows.filter((row) => row.scenario.includes('modal') || row.scenario.includes('dialog'))
  const dialogA11yRows = dialogRows.filter((row) => appViolations(row).some((v) => v.id.includes('aria') || v.id.includes('dialog') || v.id.includes('landmark')))
  if (dialogA11yRows.length) regressions.push(`Dialog and sheet captures still report axe ARIA or landmark issues in ${dialogA11yRows.length} captures.`)

  const allAppViolations = rows.flatMap(appViolations)
  const allOverlayViolations = rows.flatMap(overlayViolations)
  const appAxeSummary = summarizeViolationList(allAppViolations)
  const overlayAxeSummary = summarizeViolationList(allOverlayViolations)
  const appAxeNodeCount = countViolationNodes(allAppViolations)
  const overlayAxeNodeCount = countViolationNodes(allOverlayViolations)
  const rowsWithPanelEntryButton = rows.filter((row) => (row.inspect?.counts?.devtoolsPanelEntryButtons || 0) > 0).length
  const appAriaOrRegionNodes = appAxeSummary.filter((row) => ['aria-prohibited-attr', 'region'].includes(row.id)).reduce((sum, row) => sum + row.nodes, 0)
  const overlayAriaOrRegionNodes = overlayAxeSummary.filter((row) => ['aria-prohibited-attr', 'region'].includes(row.id)).reduce((sum, row) => sum + row.nodes, 0)
  const overlayIsolationVerdict = appAriaOrRegionNodes === 0 && rowsWithPanelEntryButton === 0
    ? 'aria-prohibited-attr and region are not app DOM issues in this production preview run; .panel-entry-btn is absent, so prior .panel-entry-btn counts are devtools overlay noise.'
    : appAriaOrRegionNodes === 0
      ? `aria-prohibited-attr and region are not app DOM issues in this run; ${overlayAriaOrRegionNodes} matching node(s) are attributable to the devtools overlay target(s).`
      : `aria-prohibited-attr or region still affect app DOM nodes in this run; ${appAriaOrRegionNodes} app node(s) remain after excluding overlay target(s).`

  const result = {
    generatedAt: new Date().toISOString(),
    baseURL,
    qaRunLabel,
    commandOutputArtifact,
    overlaySelectors,
    themes,
    widths,
    scenarios: scenarios.map(({ id, path, coverage }) => ({ id, path, coverage })),
    screenshots,
    rows,
    coverage: coverageRows(rows),
    primitiveCoverage,
    axeSummary: summarizeViolations(rows),
    appAxeSummary,
    overlayAxeSummary,
    appAxeNodeCount,
    overlayAxeNodeCount,
    overlayTargetSummary: {
      rowsWithPanelEntryButton,
      totalRows: rows.length,
    },
    overlayIsolationVerdict,
    regressions,
    unverified: [
      'Real backend WebSocket, real HLS playback and real push delivery were not verified because this matrix ran against VITE_USE_MOCK_DATA=true.',
      'Manual visual judgment beyond captured screenshots remains a human review step. The script flags overflow, focus movement and axe results, but does not replace final design review.',
      'Native device safe-area behavior was not verified. Coverage used Chromium headless viewport widths only.',
    ],
  }
  result.blocked = result.regressions.length > 0

  await fs.writeFile(path.join(outDir, 'c-ds-001-primitive-qa-results.json'), JSON.stringify(result, null, 2))
  await writeMarkdown(result)
  console.log(JSON.stringify({ blocked: result.blocked, screenshots: screenshots.length, regressions: result.regressions, axeSummary: result.axeSummary.slice(0, 8) }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
