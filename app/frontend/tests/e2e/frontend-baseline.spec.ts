import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { writeFile } from 'node:fs/promises'
import axe from 'axe-core'
import { requiredViewportMatrix } from '../../playwright.config'
import { auditVisibleActions } from '../audit/interactionAudit'
import type { InteractionAuditReport } from '../audit/interactionAudit'
import { formatBaselineStageFailure } from '../audit/baselineObservation'
import type { BaselineCollectionStage } from '../audit/baselineObservation'
import { frontendBaselineScenarios } from '../fixtures/frontend-baseline-routes'

type Theme = 'dark' | 'light'

type AuditException = {
  selector: string
  route: string
  reason: string
  owner: string
  expiryFollowup: string
}

const exceptionPath = new URL('../fixtures/interaction-audit-exceptions.json', import.meta.url)
const exceptions = JSON.parse(readFileSync(exceptionPath, 'utf8')).exceptions as AuditException[]

for (const exception of exceptions) {
  if (!exception.route || exception.route === '*' || !exception.selector || exception.selector === '*' || !exception.reason || !exception.owner || !exception.expiryFollowup) {
    throw new Error(`Interaction-audit exceptions must be narrow and owned: ${JSON.stringify(exception)}`)
  }
}

function projectIsBaseline(projectName: string) {
  return projectName.startsWith('baseline-')
}

async function prepare(page: Page, theme: Theme) {
  await page.evaluate((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
}

function withoutNarrowExceptions(route: string, violations: InteractionAuditReport['violations']) {
  return violations.filter(violation => !exceptions.some(exception => exception.route === route && exception.selector === violation.selector))
}

test('collects deterministic mock baseline across the complete viewport matrix and both themes', async ({ page }, testInfo) => {
  test.skip(!projectIsBaseline(testInfo.project.name), 'baseline harness projects only')
  test.skip(testInfo.project.name !== 'baseline-chromium', 'full viewport matrix is grouped on Chromium')
  test.setTimeout(420_000)
  await page.goto('/', { waitUntil: 'domcontentloaded' })

  const report: Array<{
    theme: Theme
    viewportClass: string
    viewport: { width: number; height: number }
    routeName: string
    route: string
    readinessSelector: string
    actionCount: number | null
    documentOverflow: number | null
    violations: InteractionAuditReport['violations']
    collectionErrors: string[]
  }> = []

  for (const theme of ['dark', 'light'] as const) {
    for (const [viewportClass, viewports] of Object.entries(requiredViewportMatrix)) {
      for (const [viewportIndex, viewport] of viewports.entries()) {
        await page.setViewportSize(viewport)
        for (const route of frontendBaselineScenarios) {
          await prepare(page, theme)
          const collectionErrors: string[] = []
          let audit: InteractionAuditReport | null = null
          let documentOverflow: number | null = null
          try {
            await page.goto(route.path, { waitUntil: 'domcontentloaded' })
            await page.locator(route.readinessSelector).waitFor({ state: 'visible', timeout: 3_000 })
            audit = await page.evaluate(auditVisibleActions as () => InteractionAuditReport)
            documentOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
          } catch (error) {
            collectionErrors.push(error instanceof Error ? error.message : String(error))
          }
          if (viewportIndex === 0) {
            try {
              await page.screenshot({
                path: testInfo.outputPath('screenshots', `${theme}-${viewportClass}-${route.routeName}-${viewport.width}x${viewport.height}.png`),
                fullPage: true,
                animations: 'disabled',
              })
            } catch (error) {
              collectionErrors.push(`screenshot: ${error instanceof Error ? error.message : String(error)}`)
            }
          }
          report.push({
            theme,
            viewportClass,
            viewport,
            routeName: route.routeName,
            route: route.path,
            readinessSelector: route.readinessSelector,
            actionCount: audit?.actions.length ?? null,
            documentOverflow,
            violations: audit ? withoutNarrowExceptions(route.path, audit.violations) : [],
            collectionErrors,
          })
          await writeFile(testInfo.outputPath('viewport-baseline.partial.json'), `${JSON.stringify({
            schemaVersion: 1,
            source: 'deterministic VITE_USE_MOCK_DATA=true Playwright collection',
            exceptionsApplied: exceptions,
            observations: report,
          }, null, 2)}\n`)
        }
      }
    }
  }

  await writeFile(testInfo.outputPath('viewport-baseline.json'), `${JSON.stringify({
    schemaVersion: 1,
    source: 'deterministic VITE_USE_MOCK_DATA=true Playwright collection',
    exceptionsApplied: exceptions,
    observations: report,
  }, null, 2)}\n`)

  expect(
    report.filter(observation => observation.collectionErrors.length > 0),
    'every viewport observation must contain genuine route evidence',
  ).toEqual([])
})

test('keeps the WebKit baseline protocol responsive across PWA navigations', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'baseline-webkit', 'WebKit regression coverage only')
  test.setTimeout(20_000)

  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await page.goto('/streamers', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.streamers-view')).toHaveCount(1)
  expect(testInfo.project.use.serviceWorkers).toBe('block')
})

for (const viewport of [{ width: 390, height: 844 }, { width: 1440, height: 900 }]) {
  for (const theme of ['dark', 'light'] as const) {
    test(`collects cross-engine a11y tree, keyboard and axe evidence at ${theme} ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
      test.skip(!projectIsBaseline(testInfo.project.name), 'baseline harness projects only')
      test.setTimeout(60_000)

      const collectionErrors: string[] = []
      let keyboardFocusCount: number | null = null
      let ariaSnapshot: string | null = null
      let seriousOrCriticalAxeViolations: unknown[] = []
      let stage: BaselineCollectionStage = 'viewport'
      const writeObservation = () => writeFile(testInfo.outputPath('a11y-baseline.json'), `${JSON.stringify({
        schemaVersion: 1,
        source: 'deterministic VITE_USE_MOCK_DATA=true Playwright collection',
        browserProject: testInfo.project.name,
        observations: [{ theme, viewport, stage, keyboardFocusCount, ariaSnapshot, seriousOrCriticalAxeViolations, collectionErrors }],
      }, null, 2)}\n`)
      try {
        stage = 'viewport'
        await writeObservation()
        await page.setViewportSize(viewport)
        stage = 'navigation'
        await writeObservation()
        await page.goto('/', { waitUntil: 'domcontentloaded' })
        await prepare(page, theme)
        await page.goto('/streamers', { waitUntil: 'domcontentloaded' })
        stage = 'readiness'
        await writeObservation()
        const streamerView = page.locator('.streamers-view')
        await expect(streamerView).toBeVisible()
        const streamerViewCount = await streamerView.count()
        if (streamerViewCount !== 1) {
          throw new Error(`expected one source-derived .streamers-view root, found ${streamerViewCount}`)
        }
        stage = 'keyboard'
        await writeObservation()
        await page.keyboard.press('Tab')
        const keyboardFocus = page.locator(':focus')
        await expect(keyboardFocus).toHaveCount(1)
        await expect(keyboardFocus).toBeVisible()
        const keyboardFocusEvidence = await keyboardFocus.evaluate((element) => ({
          isDocumentFallback: element === document.body || element === document.documentElement,
          meetsFocusableContract: element.tabIndex >= 0 && element.matches('a[href], area[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, iframe, object, embed, audio[controls], video[controls], [contenteditable]:not([contenteditable="false"]), [tabindex]'),
        }))
        if (keyboardFocusEvidence.isDocumentFallback || !keyboardFocusEvidence.meetsFocusableContract) {
          throw new Error(`keyboard focus must target a visible, focusable element instead of the document fallback: ${JSON.stringify(keyboardFocusEvidence)}`)
        }
        keyboardFocusCount = await keyboardFocus.count()
        stage = 'accessibility-tree'
        await writeObservation()
        ariaSnapshot = await page.locator('body').ariaSnapshot()
        stage = 'axe'
        await writeObservation()
        await page.addScriptTag({ content: axe.source })
        const result = await page.evaluate(async () => (window as typeof window & { axe: typeof axe }).axe.run(document))
        seriousOrCriticalAxeViolations = result.violations.filter(violation => violation.impact === 'serious' || violation.impact === 'critical')
      } catch (error) {
        collectionErrors.push(formatBaselineStageFailure(stage, error))
      }
      await writeObservation()
      expect(collectionErrors, 'cross-engine evidence collection must complete without errors').toEqual([])
      expect(keyboardFocusCount, 'keyboard evidence must be present').not.toBeNull()
      expect(ariaSnapshot, 'accessibility-tree evidence must be present').not.toBeNull()
    })
  }
}
