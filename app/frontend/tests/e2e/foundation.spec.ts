import { createRequire } from 'node:module'
import { expect, test, type Page } from '@playwright/test'
import { expectGateFailure } from '../audit/gateEvidence'

const require = createRequire(import.meta.url)
const axePath = require.resolve('axe-core/axe.min.js')
const widths = [320, 360, 390, 768, 1024, 1440]
const themes = ['dark', 'light'] as const

async function openHarness(page: Page, query = '') {
  await page.goto(`/tests/fixtures/foundation-harness/${query}`)
  await expect(page.getByRole('heading', { name: 'Recording controls' })).toBeVisible()
}

async function setThemeAndWait(page: Page, theme: 'dark' | 'light') {
  await page.evaluate(selected => { document.documentElement.dataset.theme = selected }, theme)
  const expected = theme === 'dark' ? 'rgb(248, 250, 252)' : 'rgb(15, 27, 45)'
  await page.waitForFunction(color => getComputedStyle(document.querySelector('.status-badge-success')!).color === color, expected)
}

async function assertNoOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth
    return [...document.querySelectorAll<HTMLElement>('body *')]
      .filter(element => {
        const rect = element.getBoundingClientRect()
        return rect.width > 0 && (rect.right > viewport + 1 || rect.left < -1)
      })
      .map(element => ({ tag: element.tagName, className: element.className, rect: element.getBoundingClientRect().toJSON() }))
  })
  expect(overflow, `overflowing elements: ${JSON.stringify(overflow)}`).toEqual([])
}

async function assertTouchTargets(page: Page) {
  const undersized = await page.locator('button, input, select, a[href]').evaluateAll(elements => elements
    .filter(element => (element as HTMLElement).offsetParent !== null)
    .map(element => {
      const rect = element.getBoundingClientRect()
      return { name: element.getAttribute('aria-label') || element.textContent?.trim(), width: rect.width, height: rect.height }
    })
    .filter(rect => rect.width < 43.99 || rect.height < 43.99))
  expect(undersized, `undersized targets: ${JSON.stringify(undersized)}`).toEqual([])
}

async function assertAxe(page: Page) {
  await page.addScriptTag({ path: axePath })
  const violations = await page.evaluate(async () => {
    const result = await window.axe.run(document, { resultTypes: ['violations'] })
    return result.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')
  })
  expect(violations, JSON.stringify(violations, null, 2)).toEqual([])
}

test('matrix: themes, viewport widths, touch targets, 200% text, states and axe', async ({ page }) => {
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 768 ? 844 : 900 })
    for (const theme of themes) {
      await openHarness(page)
      await setThemeAndWait(page, theme)
      for (const state of ['loaded', 'empty', 'loading', 'error', 'disabled']) {
        await page.getByRole('button', { name: state, exact: true }).click()
        await expect(page.locator('main')).toHaveAttribute('data-state', state)
      }
      await assertTouchTargets(page)
      await assertNoOverflow(page)
      await page.evaluate(() => { document.documentElement.style.fontSize = '200%' })
      await assertNoOverflow(page)
      await page.evaluate(() => { document.documentElement.style.fontSize = '' })
      await assertAxe(page)
    }
  }
})

test('modal and sheet trap focus, close on Escape, and restore launch focus', async ({ page }) => {
  await openHarness(page)
  const modalLauncher = page.getByRole('button', { name: 'Open dialog' })
  await modalLauncher.click()
  await expect(page.getByRole('dialog', { name: 'Confirm recording' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog', { name: 'Confirm recording' })).toBeHidden()
  await expect(modalLauncher).toBeFocused()

  const sheetLauncher = page.getByRole('button', { name: 'Open sheet' })
  await sheetLauncher.click()
  const sheet = page.getByRole('dialog', { name: 'Recording filters' })
  await expect(sheet).toBeVisible()
  await expect(sheet.locator('button').first()).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(sheet.locator('button').last()).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(sheet).toBeHidden()
  await expect(sheetLauncher).toBeFocused()
})

test('reduced motion disables pulsing status animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openHarness(page)
  await page.getByRole('button', { name: 'loading', exact: true }).click()
  const animation = await page.locator('.status-badge-pulse .status-badge-dot-mark').evaluate(element => getComputedStyle(element).animationName)
  expect(animation).toBe('none')
})

test('negative browser fixtures fail the intended blocking gates', async ({ page }) => {
  await openHarness(page, '?broken=touch')
  await expectGateFailure(() => assertTouchTargets(page), /undersized targets/)
  await openHarness(page, '?broken=overflow')
  await page.setViewportSize({ width: 320, height: 844 })
  await expectGateFailure(() => assertNoOverflow(page), /overflowing elements/)
  await openHarness(page, '?broken=contrast')
  await expectGateFailure(() => assertAxe(page), /color-contrast/)
})

test('captures current light/dark mobile/desktop foundation evidence', async ({ page }, testInfo) => {
  for (const [label, width, height] of [['mobile', 390, 844], ['desktop', 1440, 900]] as const) {
    await page.setViewportSize({ width, height })
    for (const theme of themes) {
      await openHarness(page)
      await setThemeAndWait(page, theme)
      await page.screenshot({
        path: testInfo.outputPath(`foundation-${label}-${theme}.png`),
        fullPage: true,
      })
    }
  }
})

declare global {
  interface Window { axe: { run: (context: Document, options: unknown) => Promise<{ violations: Array<{ impact: string | null }> }> } }
}
