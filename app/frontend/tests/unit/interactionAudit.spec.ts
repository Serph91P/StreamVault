import { afterEach, describe, expect, it } from 'vitest'
import { auditVisibleActions } from '../audit/interactionAudit'

function setRect(element: HTMLElement, rect: Partial<DOMRect>) {
  Object.defineProperty(element, 'getBoundingClientRect', {
    configurable: true,
    value: () => ({
      x: 0,
      y: 0,
      top: 0,
      left: 0,
      right: 48,
      bottom: 48,
      width: 48,
      height: 48,
      toJSON: () => ({}),
      ...rect,
    }),
  })
}

afterEach(() => {
  document.body.replaceChildren()
})

describe('auditVisibleActions', () => {
  it('reports a rendered undersized enabled button', () => {
    const button = document.createElement('button')
    button.textContent = 'Save'
    document.body.append(button)
    setRect(button, { width: 32, height: 40, right: 32, bottom: 40 })

    const report = auditVisibleActions(document, { hitTest: () => button })

    expect(report.violations).toContainEqual(expect.objectContaining({
      kind: 'undersized',
      width: 32,
      height: 40,
    }))
  })

  it('reports intersecting visible action targets', () => {
    const first = document.createElement('button')
    const second = document.createElement('button')
    document.body.append(first, second)
    setRect(first, { left: 0, top: 0, width: 48, height: 48, right: 48, bottom: 48 })
    setRect(second, { left: 40, top: 0, width: 48, height: 48, right: 88, bottom: 48 })

    const report = auditVisibleActions(document, { hitTest: () => first })

    expect(report.violations).toContainEqual(expect.objectContaining({ kind: 'overlap' }))
  })

  it('reports a visible target whose representative point is covered by another element', () => {
    const button = document.createElement('button')
    const cover = document.createElement('div')
    document.body.append(button, cover)
    setRect(button, { width: 48, height: 48, right: 48, bottom: 48 })
    setRect(cover, { width: 48, height: 48, right: 48, bottom: 48 })

    const report = auditVisibleActions(document, { hitTest: () => cover })

    expect(report.violations).toContainEqual(expect.objectContaining({ kind: 'hit-test' }))
  })

  it('excludes hidden and disabled controls without treating them as viable hit targets', () => {
    const hidden = document.createElement('button')
    hidden.style.display = 'none'
    const disabled = document.createElement('button')
    disabled.disabled = true
    document.body.append(hidden, disabled)
    setRect(hidden, { width: 20, height: 20, right: 20, bottom: 20 })
    setRect(disabled, { width: 20, height: 20, right: 20, bottom: 20 })

    const report = auditVisibleActions(document, { hitTest: () => null })

    expect(report.actions).toHaveLength(0)
    expect(report.violations).toHaveLength(0)
  })

  it('audits a visible summary even while its details content is closed', () => {
    const details = document.createElement('details')
    const summary = document.createElement('summary')
    summary.textContent = 'More actions'
    details.append(summary)
    document.body.append(details)
    setRect(summary, { width: 32, height: 32, right: 32, bottom: 32 })

    const report = auditVisibleActions(document, { hitTest: () => summary })

    expect(report.actions).toHaveLength(1)
    expect(report.violations).toContainEqual(expect.objectContaining({ kind: 'undersized' }))
  })

  it('audits visually exposed aria-hidden controls instead of treating semantic debt as invisibility', () => {
    const button = document.createElement('button')
    button.setAttribute('aria-hidden', 'true')
    document.body.append(button)
    setRect(button, { width: 32, height: 32, right: 32, bottom: 32 })

    const report = auditVisibleActions(document, { hitTest: () => button })

    expect(report.actions).toHaveLength(1)
    expect(report.violations).toContainEqual(expect.objectContaining({ kind: 'undersized' }))
  })

  it('audits role slider controls even when missing tabindex', () => {
    const slider = document.createElement('div')
    slider.setAttribute('role', 'slider')
    document.body.append(slider)
    setRect(slider, { width: 32, height: 32, right: 32, bottom: 32 })

    const report = auditVisibleActions(document, { hitTest: () => slider })

    expect(report.actions).toHaveLength(1)
    expect(report.violations).toContainEqual(expect.objectContaining({ kind: 'undersized' }))
  })
})
