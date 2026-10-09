import { expect, test } from '@playwright/test'
import axe from 'axe-core'
import type { Page } from '@playwright/test'

type Theme = 'dark' | 'light'

const widths = [360, 390, 450, 768, 1024, 1440, 1920] as const
const activeRoutes = [
  '/',
  '/streamers',
  '/videos',
  '/settings',
  '/admin',
  '/subscriptions',
  '/add-streamer',
  '/videos/1',
  '/live/streamer-alpha',
  '/auth/login',
  '/onboarding?step=recording',
] as const

test.use({ locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' })

async function preparePage(page: Page, theme: Theme = 'light') {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('streamvault-theme', selectedTheme)
  }, theme)
  await page.route('**/auth/setup', route => route.fulfill({ json: { setup_required: false, welcome_completed: false } }))
  await page.route('**/api/twitch/connection-status', route => route.fulfill({ json: { connected: false } }))
  await page.route('**/api/recording/settings', route => route.fulfill({ json: {
    enabled: true,
    default_quality: 'best',
    filename_template: '{streamer}_{date}',
    filename_preset: 'default',
    use_chapters: true,
    use_category_as_chapter_title: true,
    supported_codecs: ['h264'],
    preferred_codec: 'h264',
    fallback_enabled: true,
  } }))
}

async function disableMotion(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        scroll-behavior: auto !important;
      }
    `,
  })
}

type LoginCaptureState = {
  panel: { width: number; height: number; opacity: number; visible: boolean }
  controls: Array<{
    label: string
    width: number
    height: number
    opacity: number
    visible: boolean
    ancestorOpacities: number[]
  }>
  panelAncestorOpacities: number[]
}

async function getLoginCaptureState(page: Page): Promise<LoginCaptureState> {
  return page.locator('.login-card.base-panel').evaluate((panel) => {
    const panelElement = panel as HTMLElement
    const opacitiesTo = (element: HTMLElement, last: HTMLElement | null) => {
      const opacities: number[] = []
      for (let current: HTMLElement | null = element; current; current = current.parentElement) {
        opacities.push(Number(getComputedStyle(current).opacity))
        if (current === last) break
      }
      return opacities
    }
    const measured = (element: HTMLElement, label: string) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return {
        label,
        width: rect.width,
        height: rect.height,
        opacity: Number(style.opacity),
        visible: style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0,
        ancestorOpacities: opacitiesTo(element, panelElement),
      }
    }
    return {
      panel: measured(panelElement, 'panel'),
      controls: [
        measured(document.querySelector('#username') as HTMLElement, 'Username'),
        measured(document.querySelector('#password') as HTMLElement, 'Password'),
        measured(document.querySelector('button[type="submit"]') as HTMLElement, 'Sign In'),
      ],
      panelAncestorOpacities: opacitiesTo(panelElement, null),
    }
  })
}

async function waitForLoginCaptureReadiness(page: Page) {
  await expect(page.locator('.login-card.base-panel')).toBeVisible()
  await expect(page.getByLabel('Username')).toBeVisible()
  await expect(page.getByLabel('Password')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign In' })).toBeVisible()
  await expect.poll(async () => {
    const state = await getLoginCaptureState(page)
    return state.panel.visible
      && state.panel.width > 0
      && state.panel.height > 0
      && state.panel.opacity === 1
      && state.panelAncestorOpacities.every(opacity => opacity === 1)
      && state.controls.every(control => control.visible
        && control.width > 0
        && control.height > 0
        && control.opacity === 1
        && control.ancestorOpacities.every(opacity => opacity === 1))
  }, { timeout: 10_000 }).toBe(true)
}

async function assertRenderedContract(page: Page, width: number) {
  const issues = await page.evaluate(({ mobileWidth }) => {
    const visible = (element: Element) => {
      if (element.closest('details:not([open])')) return false
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0
    }
    const controls = Array.from(document.querySelectorAll(
      'button:not([disabled]), [role="button"]:not([aria-disabled="true"]), a.btn, a[class*="-btn"], a[class*="button"]',
    )).filter(visible)
    const smallControls = controls.flatMap((element) => {
      const rect = element.getBoundingClientRect()
      if (rect.width >= 43.9 && rect.height >= 43.9) return []
      return [{
        label: element.getAttribute('aria-label') || element.textContent?.trim() || element.tagName,
        width: Math.round(rect.width * 10) / 10,
        height: Math.round(rect.height * 10) / 10,
      }]
    })
    const smallFonts = mobileWidth <= 450
      ? Array.from(document.querySelectorAll('input:not([type="hidden"]), select, textarea'))
          .filter(visible)
          .flatMap(element => Number.parseFloat(getComputedStyle(element).fontSize) < 16
            ? [element.getAttribute('aria-label') || element.id || element.tagName]
            : [])
      : []
    const currentOutsideViewport = Array.from(document.querySelectorAll('[aria-current], [aria-selected="true"]'))
      .filter(visible)
      .flatMap((element) => {
        const rect = element.getBoundingClientRect()
        const scroller = element.closest<HTMLElement>('[class*="scroll"], [role="tablist"]')
        const hasHorizontalScroller = Boolean(scroller && scroller.scrollWidth > scroller.clientWidth)
        return rect.left >= -1 && rect.right <= innerWidth + 1 || hasHorizontalScroller
          ? []
          : [element.getAttribute('aria-label') || element.textContent?.trim() || element.tagName]
      })
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      smallControls,
      smallFonts,
      currentOutsideViewport,
    }
  }, { mobileWidth: width })

  expect(issues.overflow).toBe(0)
  expect(issues.smallControls).toEqual([])
  expect(issues.smallFonts).toEqual([])
  expect(issues.currentOutsideViewport).toEqual([])
}

test('active PR5 routes satisfy responsive geometry at the viewport matrix', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  test.setTimeout(120_000)
  await preparePage(page)

  for (const width of widths) {
    await page.setViewportSize({ width, height: width <= 450 ? 844 : 900 })
    for (const route of activeRoutes) {
      await page.goto(route)
      await page.locator('body').waitFor({ state: 'visible' })
      await page.waitForTimeout(100)
      await assertRenderedContract(page, width)
    }
  }
})

test('mobile routed content clears the visible connectivity pill', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })
  })
  await preparePage(page)
  await page.goto('/add-streamer')
  const pill = page.locator('.mobile-connectivity-pill')
  await expect(pill).toBeVisible()
  const finalAction = page.locator('main.main-content button:not([disabled])').last()
  await finalAction.scrollIntoViewIfNeeded()

  const gap = await Promise.all([finalAction.boundingBox(), pill.boundingBox()])
    .then(([action, status]) => status!.y - (action!.y + action!.height))
  expect(gap).toBeGreaterThanOrEqual(8)
})

test('System hub keeps settings, admin and subscriptions reachable on desktop and mobile', async ({ page }, testInfo) => {
  const widths = testInfo.project.name === 'mobile' ? [390] : [1440]

  for (const width of widths) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await preparePage(page)
    await page.goto('/')
    const shellNav = page.locator(width === 390 ? '.bottom-nav' : '.sidebar-nav')
    await expect(shellNav).toBeVisible()
    await expect(shellNav).toHaveCSS('backdrop-filter', 'none')
    await page.getByRole('link', { name: 'System', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'System', exact: true })).toBeVisible()

    for (const destination of [
      { label: 'Settings', path: '/settings' },
      { label: 'Admin tools', path: '/admin' },
      { label: 'Subscriptions', path: '/subscriptions' },
    ]) {
      await page.getByRole('link', { name: destination.label, exact: true }).click()
      await expect(page).toHaveURL(new RegExp(`${destination.path}$`))
      await page.goBack()
      await expect(page.getByRole('heading', { name: 'System', exact: true })).toBeVisible()
    }
  }
})

test('System subpages provide a keyboard-accessible Back to System link on desktop and mobile', async ({ page }, testInfo) => {
  const widths = testInfo.project.name === 'mobile' ? [390] : [1440]

  for (const width of widths) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
    await preparePage(page)

    for (const path of ['/settings', '/admin', '/subscriptions']) {
      await page.goto(path)
      const back = page.getByRole('link', { name: 'Back to System', exact: true })
      await expect(back).toBeVisible()
      await back.focus()
      await expect(back).toBeFocused()
      const box = await back.boundingBox()
      expect(box?.height).toBeGreaterThanOrEqual(44)
      await page.keyboard.press('Enter')
      await expect(page).toHaveURL(/\/system$/)
    }
  }
})

test('onboarding quality control keeps a visible native affordance and the primary action reachable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await preparePage(page)
  await page.goto('/onboarding?step=recording')

  const quality = page.getByLabel('Default Quality')
  await expect(quality).toBeVisible()
  await expect(quality).toHaveCSS('appearance', 'auto')
  const qualityBox = await quality.boundingBox()
  expect(qualityBox?.height).toBeGreaterThanOrEqual(44)

  const save = page.getByRole('button', { name: 'Save & Continue' })
  await save.scrollIntoViewIfNeeded()
  await expect(save).toBeVisible()
  const saveBox = await save.boundingBox()
  expect(saveBox?.height).toBeGreaterThanOrEqual(44)
})

test('welcome distinguishes forbidden and unreachable setup without showing the admin form', async ({ page }) => {
  await page.route('**/auth/setup', route => route.fulfill({ status: 403 }))
  await page.goto('/welcome')
  await expect(page.getByRole('alert')).toContainText('Access to setup is forbidden.')
  await expect(page.getByText('Create your administrator credentials')).toHaveCount(0)

  await page.unroute('**/auth/setup')
  await page.route('**/auth/setup', route => route.abort('failed'))
  await page.reload()
  await expect(page.getByRole('alert')).toContainText('Could not reach StreamVault setup.')
  await expect(page.getByText('Create your administrator credentials')).toHaveCount(0)
})

test('login and onboarding use opaque panels without backdrop blur across themes and form factors', async ({ page }, testInfo) => {
  const widths = testInfo.project.name === 'mobile' ? [390] : [1440]

  for (const theme of ['light', 'dark'] as const) {
    for (const width of widths) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
      await preparePage(page, theme)

      for (const [route, label] of [['/auth/login', 'Username'], ['/onboarding?step=recording', 'Default Quality']] as const) {
        await page.goto(route)
        const panel = page.locator(route === '/auth/login' ? '.login-card.base-panel' : '.wizard-card.base-panel')
        if (route === '/auth/login') {
          // A DOM-visible login panel starts fully transparent during scaleIn. Capture
          // only after the measured panel, controls, and every opacity ancestor are ready.
          await waitForLoginCaptureReadiness(page)
        } else {
          await expect(panel).toBeVisible()
        }
        await expect(panel).toHaveCSS('backdrop-filter', 'none')
        const panelStyle = await panel.evaluate(element => {
          const style = getComputedStyle(element)
          return { background: style.backgroundColor, image: style.backgroundImage }
        })
        expect(panelStyle.background).toMatch(/^rgb\(/)
        expect(panelStyle.image).toBe('none')

        const control = page.getByLabel(label)
        await control.focus()
        await expect(control).toBeFocused()
        if (route === '/auth/login') {
          await expect.poll(async () => {
            const state = await getLoginCaptureState(page)
            return state.panel.opacity === 1
              && state.panelAncestorOpacities.every(opacity => opacity === 1)
              && state.controls.every(candidate => candidate.opacity === 1
                && candidate.visible
                && candidate.ancestorOpacities.every(opacity => opacity === 1))
          }).toBe(true)
        }
        const surface = route === '/auth/login' ? 'login' : 'onboarding'
        const fileName = `${surface}-${theme}-${width}-${testInfo.project.name}.png`
        await page.screenshot({
          path: testInfo.outputPath(fileName),
          fullPage: false,
        })
      }
    }
  }
})

test('active PR5 route fixtures have no serious or critical Axe violations', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop')
  test.setTimeout(120_000)

  for (const theme of ['light', 'dark'] as const) {
    await preparePage(page, theme)
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 900 })
      for (const route of activeRoutes) {
        await page.goto(route)
        await page.waitForTimeout(500)
        await disableMotion(page)
        await page.addScriptTag({ content: axe.source })
        const violations = await page.evaluate(async () => {
          const result = await (window as typeof window & { axe: typeof axe }).axe.run(document)
          return result.violations
            .filter(violation => violation.impact === 'serious' || violation.impact === 'critical')
            .map(violation => ({
              id: violation.id,
              targets: violation.nodes.map(node => node.target),
            }))
        })
        expect(violations, `${theme} ${width}px ${route}`).toEqual([])
      }
    }
  }
})

const snapshots = [
  { name: 'shell-light-360', route: '/', width: 360, height: 800, theme: 'light' },
  { name: 'shell-dark-360', route: '/', width: 360, height: 800, theme: 'dark' },
  { name: 'shell-light-1440', route: '/', width: 1440, height: 900, theme: 'light' },
  { name: 'shell-dark-1440', route: '/', width: 1440, height: 900, theme: 'dark' },
  { name: 'videos-filters-light-360', route: '/videos', width: 360, height: 800, theme: 'light', filters: true },
  { name: 'videos-filters-dark-360', route: '/videos', width: 360, height: 800, theme: 'dark', filters: true },
  { name: 'videos-filters-long-450', route: '/videos', width: 450, height: 900, theme: 'light', filters: true, longLabel: true },
  { name: 'settings-light-390', route: '/settings', width: 390, height: 844, theme: 'light' },
  { name: 'settings-dark-1024', route: '/settings', width: 1024, height: 768, theme: 'dark' },
  { name: 'onboarding-light-390', route: '/onboarding?step=recording', width: 390, height: 844, theme: 'light' },
  { name: 'onboarding-dark-390', route: '/onboarding?step=recording', width: 390, height: 844, theme: 'dark' },
] as const

for (const snapshot of snapshots) {
  test(`${snapshot.name} visual`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop')
    await page.setViewportSize({ width: snapshot.width, height: snapshot.height })
    await preparePage(page, snapshot.theme)
    await page.goto(snapshot.route)
    if (snapshot.route === '/') {
      await expect(page.getByRole('heading', { name: '2 streamers live now' })).toBeVisible()
    }
    if (snapshot.route === '/settings') {
      await expect(page.getByRole('heading', { name: 'Twitch Connection', exact: true }).first()).toBeVisible()
    }
    if (snapshot.route.startsWith('/onboarding')) {
      await expect(page.getByRole('heading', { name: 'Recording Defaults' })).toBeVisible()
    }
    if ('filters' in snapshot && snapshot.filters) {
      await page.getByRole('button', { name: 'Filters' }).click()
    }
    if ('longLabel' in snapshot && snapshot.longLabel) {
      await page.getByLabel('Filter videos by streamer').locator('option').nth(1).evaluate((option) => {
        option.textContent = 'A streamer name deliberately long enough to require calm reflow'
      })
      await page.getByLabel('Filter videos by streamer').selectOption({ index: 1 })
    }
    await disableMotion(page)
    await expect(page).toHaveScreenshot(`${snapshot.name}.png`, {
      animations: 'disabled',
      caret: 'hide',
      fullPage: false,
      mask: [page.locator('img, video, time, .streamer-avatar')],
      maxDiffPixels: 600,
      scale: 'css',
    })
  })
}
