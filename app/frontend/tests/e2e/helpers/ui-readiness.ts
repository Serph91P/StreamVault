import { expect, type Page } from '@playwright/test'

interface ReadinessState {
  missingSelectors: string[]
  unrenderedSelectors: string[]
  translucentSelectors: string[]
  activeFiniteAnimations: number
}

export async function getUiReadinessState(page: Page, requiredSelectors: string[]): Promise<ReadinessState> {
  return page.evaluate((selectors) => {
    const required = selectors.flatMap((selector) => Array.from(document.querySelectorAll<HTMLElement>(selector)))
    const missingSelectors = selectors.filter((selector) => !document.querySelector(selector))
    const isRendered = (element: HTMLElement) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && rect.width > 0
        && rect.height > 0
    }
    const hasOpaqueAncestorChain = (element: HTMLElement) => {
      for (let current: HTMLElement | null = element; current; current = current.parentElement) {
        if (Number(getComputedStyle(current).opacity) < 0.999) return false
      }
      return true
    }
    const relevantAnimation = (animation: Animation) => {
      const target = animation.effect instanceof KeyframeEffect
        ? animation.effect.target
        : null
      return target instanceof HTMLElement
        && required.some((element) => element.contains(target) || target.contains(element))
    }
    const activeFiniteAnimations = document.getAnimations()
      .filter(relevantAnimation)
      .filter((animation) => {
        const endTime = Number(animation.effect?.getComputedTiming().endTime)
        const isUnfinished = animation.playState === 'running'
          || animation.playState === 'paused'
          || animation.pending
        // A cancelled animation is idle and no longer has work that can finish.
        return Number.isFinite(endTime)
          && endTime > 0
          && isUnfinished
      }).length

    return {
      missingSelectors,
      unrenderedSelectors: selectors.filter((selector) => {
        const matches = Array.from(document.querySelectorAll<HTMLElement>(selector))
        return matches.length > 0 && matches.some((element) => !isRendered(element))
      }),
      translucentSelectors: selectors.filter((selector) => {
        const matches = Array.from(document.querySelectorAll<HTMLElement>(selector))
        return matches.length > 0 && matches.some((element) => !hasOpaqueAncestorChain(element))
      }),
      activeFiniteAnimations,
    }
  }, requiredSelectors)
}

export async function waitForUiReadiness(page: Page, requiredSelectors: string[]) {
  expect(requiredSelectors.length, 'Readiness requires at least one exact content selector').toBeGreaterThan(0)

  await expect.poll(
    () => getUiReadinessState(page, requiredSelectors),
    { timeout: 10_000, message: `UI did not become semantically ready: ${requiredSelectors.join(', ')}` },
  ).toEqual({
    missingSelectors: [],
    unrenderedSelectors: [],
    translucentSelectors: [],
    activeFiniteAnimations: 0,
  })
}
