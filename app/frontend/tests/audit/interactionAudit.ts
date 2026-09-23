export const actionableSelector = [
  'button',
  'a[href]',
  'input:not([type="hidden"])',
  'select',
  'textarea',
  'summary',
  '[role="button"]',
  '[role="link"]',
  '[role="tab"]',
  '[role="switch"]',
  '[role="checkbox"]',
  '[role="radio"]',
  '[role="slider"]',
  '[role="menuitem"]',
  '[role="option"]',
  '[tabindex]:not([tabindex="-1"])',
].join(', ')

export type AuditViolationKind = 'hit-test' | 'overlap' | 'undersized'

export interface ActionMeasurement {
  selector: string
  tagName: string
  accessibleName: string
  width: number
  height: number
  x: number
  y: number
}

export interface AuditViolation extends ActionMeasurement {
  kind: AuditViolationKind
  relatedSelector?: string
}

export interface InteractionAuditReport {
  actions: ActionMeasurement[]
  violations: AuditViolation[]
}

export interface InteractionAuditOptions {
  minimumSize?: number
  hitTest?: (x: number, y: number) => Element | null
  selector?: string
}

export function auditVisibleActions(root: ParentNode = document, options: InteractionAuditOptions = {}): InteractionAuditReport {
  const minimumSize = options.minimumSize ?? 44
  const hitTest = options.hitTest ?? ((x, y) => document.elementFromPoint(x, y))
  // Keep every dependency inside this function. Playwright serializes this exact
  // function into the browser, so route collection and Vitest exercise one audit.
  const selector = options.selector ?? [
    'button', 'a[href]', 'input:not([type="hidden"])', 'select', 'textarea', 'summary',
    '[role="button"]', '[role="link"]', '[role="tab"]', '[role="switch"]',
    '[role="checkbox"]', '[role="radio"]', '[role="slider"]', '[role="menuitem"]', '[role="option"]',
    '[tabindex]:not([tabindex="-1"])',
  ].join(', ')
  const isVisibleAction = (element: HTMLElement) => {
    if (element.matches(':disabled, [aria-disabled="true"]')) return false
    if (element.closest('[inert]')) return false
    const closedDetails = element.closest('details:not([open])')
    if (closedDetails && !element.closest('summary')) return false
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return style.display !== 'none'
      && style.visibility !== 'hidden'
      && Number(style.opacity || '1') > 0
      && rect.width > 0
      && rect.height > 0
  }
  const describe = (element: HTMLElement, index: number) => {
    const testId = element.getAttribute('data-testid')
    if (testId) return `[data-testid="${testId}"]`
    const id = element.id
    if (id) return `#${id}`
    const name = element.getAttribute('aria-label') || element.textContent?.trim()
    return name ? `${element.tagName.toLowerCase()}[name="${name.slice(0, 80)}"]` : `${element.tagName.toLowerCase()}:nth-of-type(${index + 1})`
  }
  const intersects = (first: DOMRect, second: DOMRect) => first.left < second.right
    && first.right > second.left
    && first.top < second.bottom
    && first.bottom > second.top
  const elements = Array.from(root.querySelectorAll<HTMLElement>(selector))
    .filter(isVisibleAction)
  const actions = elements.map((element, index) => {
    const rect = element.getBoundingClientRect()
    return {
      element,
      rect,
      measurement: {
        selector: describe(element, index),
        tagName: element.tagName.toLowerCase(),
        accessibleName: element.getAttribute('aria-label') || element.textContent?.trim() || '',
        width: Number(rect.width.toFixed(2)),
        height: Number(rect.height.toFixed(2)),
        x: Number(rect.x.toFixed(2)),
        y: Number(rect.y.toFixed(2)),
      },
    }
  })

  const violations: AuditViolation[] = []
  for (const action of actions) {
    const { element, rect, measurement } = action
    if (rect.width < minimumSize || rect.height < minimumSize) {
      violations.push({ kind: 'undersized', ...measurement })
    }

    const point = hitTest(rect.left + rect.width / 2, rect.top + rect.height / 2)
    if (point && point !== element && !element.contains(point)) {
      violations.push({ kind: 'hit-test', ...measurement, relatedSelector: describe(point as HTMLElement, 0) })
    }
  }

  for (let index = 0; index < actions.length; index += 1) {
    for (let otherIndex = index + 1; otherIndex < actions.length; otherIndex += 1) {
      const first = actions[index]
      const second = actions[otherIndex]
      if (intersects(first.rect, second.rect)) {
        violations.push({ kind: 'overlap', ...first.measurement, relatedSelector: second.measurement.selector })
      }
    }
  }

  return {
    actions: actions.map(({ measurement }) => measurement),
    violations,
  }
}
