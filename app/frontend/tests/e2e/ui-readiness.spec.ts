import { expect, test } from '@playwright/test'
import axe from 'axe-core'
import { getUiReadinessState, waitForUiReadiness } from './helpers/ui-readiness'

test('readiness waits for every required rendered node and its finite ancestor animation', async ({ page }) => {
  await page.setContent(`
    <style>
      @keyframes reveal { from { opacity: .2; transform: translateY(4px) } to { opacity: 1; transform: none } }
      #fourth { animation: reveal 500ms linear 100ms backwards; }
    </style>
    <main>
      <h1>Streamers</h1>
      <article class="streamer-wrapper">one</article>
      <article class="streamer-wrapper">two</article>
      <article class="streamer-wrapper">three</article>
      <article id="fourth" class="streamer-wrapper"><a class="view-details-link" href="#details">View details</a></article>
    </main>
  `)

  await page.waitForFunction(() => document.querySelector('#fourth')?.getAnimations().some((animation) => {
    const endTime = Number(animation.effect?.getComputedTiming().endTime)
    return Number.isFinite(endTime) && endTime > 0 && animation.playState === 'running'
  }))

  let resolved = false
  const readiness = waitForUiReadiness(page, ['h1', '.streamer-wrapper', '#fourth .view-details-link'])
    .then(() => { resolved = true })
  await Promise.resolve()
  expect(resolved).toBe(false)

  await readiness
  const finalState = await page.locator('#fourth .view-details-link').evaluate((node) => {
    const opacities: number[] = []
    for (let current: HTMLElement | null = node as HTMLElement; current; current = current.parentElement) {
      opacities.push(Number(getComputedStyle(current).opacity))
    }
    return {
      rect: node.getBoundingClientRect().toJSON(),
      opacities,
      finiteAnimations: document.getAnimations().filter((animation) => {
        const endTime = Number(animation.effect?.getComputedTiming().endTime)
        return Number.isFinite(endTime) && endTime > 0
      }).map((animation) => animation.playState),
    }
  })

  expect(finalState.rect.width).toBeGreaterThan(0)
  expect(finalState.rect.height).toBeGreaterThan(0)
  expect(finalState.opacities.every((opacity) => opacity === 1)).toBe(true)
  expect(finalState.finiteAnimations.every((state) => state === 'finished')).toBe(true)
})

test('readiness keeps a paused finite animation pending until it resumes and finishes', async ({ page }) => {
  await page.setContent('<main><div id="required-node">Required content</div></main>')
  await page.locator('#required-node').evaluate(async (node) => {
    const animation = node.animate(
      [{ transform: 'translateY(4px)' }, { transform: 'none' }],
      { duration: 1_000, fill: 'both' },
    )
    animation.pause()
    await animation.ready
  })

  const pausedState = await getUiReadinessState(page, ['#required-node'])
  expect(pausedState.activeFiniteAnimations).toBe(1)

  let resolved = false
  const readiness = waitForUiReadiness(page, ['#required-node'])
    .then(() => { resolved = true })
  await page.waitForTimeout(150)
  expect(resolved).toBe(false)

  await page.locator('#required-node').evaluate((node) => {
    const [animation] = node.getAnimations()
    animation.play()
  })
  await readiness

  await expect.poll(() => page.locator('#required-node').evaluate((node) => (
    node.getAnimations().map((animation) => animation.playState)
  ))).toEqual(['finished'])
})

test('readiness ignores cancelled finite and infinite decorative animations', async ({ page }) => {
  await page.setContent('<main><div id="required-node">Required content</div></main>')
  await page.locator('#required-node').evaluate(async (node) => {
    const cancelled = node.animate(
      [{ transform: 'translateY(4px)' }, { transform: 'none' }],
      { duration: 5_000, fill: 'both' },
    )
    cancelled.cancel()

    const decorative = node.animate(
      [{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }],
      { duration: 1_000, iterations: Infinity },
    )
    await decorative.ready
  })

  await expect.poll(() => getUiReadinessState(page, ['#required-node'])).toEqual({
    missingSelectors: [],
    unrenderedSelectors: [],
    translucentSelectors: [],
    activeFiniteAnimations: 0,
  })
})

test('the unchanged Axe contrast rule detects a visible negative control as a violation, not incomplete', async ({ page }) => {
  await page.setContent(`
    <main style="background:#fff">
      <div id="ux07-negative-control" style="display:block;width:220px;height:40px;color:#ddd;background:#fff;font:16px/40px Arial">
        VISIBLE CONTRAST CONTROL
      </div>
    </main>
  `)
  await page.addScriptTag({ content: axe.source })

  const result = await page.evaluate(async () => {
    const browserAxe = (window as typeof window & { axe: typeof axe }).axe
    return browserAxe.run(document, {
      runOnly: { type: 'rule', values: ['color-contrast', 'target-size'] },
    })
  })
  const violationTargets = result.violations
    .filter((violation) => violation.id === 'color-contrast')
    .flatMap((violation) => violation.nodes.flatMap((node) => node.target))
  const incompleteTargets = result.incomplete
    .filter((entry) => entry.id === 'color-contrast')
    .flatMap((entry) => entry.nodes.flatMap((node) => node.target))

  expect(violationTargets).toContain('#ux07-negative-control')
  expect(incompleteTargets).not.toContain('#ux07-negative-control')
})
