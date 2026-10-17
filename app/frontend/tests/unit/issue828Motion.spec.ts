import { afterEach, describe, expect, it, vi } from 'vitest'
import { isMotionSettled } from '../fixtures/issue828Motion'

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks() })

function panel() {
  const ancestor = document.createElement('section')
  const dialog = document.createElement('dialog')
  dialog.open = true
  const button = document.createElement('button')
  ancestor.append(dialog)
  dialog.append(button)
  document.body.append(ancestor)
  for (const element of [ancestor, dialog, button, document.body, document.documentElement]) {
    element.style.opacity = '1'
    Object.defineProperty(element, 'getAnimations', { configurable: true, value: vi.fn(() => []) })
  }
  return { ancestor, dialog, button }
}

describe('physical motion readiness contract (no browser acceptance)', () => {
  it('rejects Vue entry before animations have even started, then accepts actual completion', () => {
    const { dialog } = panel()
    dialog.className = 'slide-panel-enter-from slide-panel-enter-active'
    dialog.style.opacity = '0'
    expect(dialog.getAnimations()).toEqual([])
    expect(isMotionSettled(dialog)).toBe(false)
    dialog.style.opacity = '1'
    expect(isMotionSettled(dialog)).toBe(false)
    dialog.className = ''
    expect(isMotionSettled(dialog)).toBe(true)
  })

  it('requires visible ancestors and controls, not just the dialog own opacity', () => {
    const { ancestor, button } = panel()
    ancestor.style.opacity = '0.5'
    expect(isMotionSettled(button)).toBe(false)
    ancestor.style.opacity = '1'
    ancestor.style.visibility = 'hidden'
    expect(isMotionSettled(button)).toBe(false)
    ancestor.style.visibility = 'visible'
    expect(isMotionSettled(button)).toBe(true)
  })

  it.each(['running', 'paused', 'pending'])('rejects relevant finite %s motion', state => {
    const { ancestor, button } = panel()
    const animation = {
      pending: state === 'pending', playState: state === 'pending' ? 'idle' : state,
      effect: { getComputedTiming: () => ({ endTime: 300 }) }
    }
    vi.mocked(ancestor.getAnimations).mockReturnValue([animation as unknown as Animation])
    expect(isMotionSettled(button)).toBe(false)
    animation.pending = false
    animation.playState = 'finished'
    expect(isMotionSettled(button)).toBe(true)
  })

  it('does not wait forever for unrelated infinite activity indicators', () => {
    const { dialog } = panel()
    vi.mocked(dialog.getAnimations).mockReturnValue([{
      pending: false, playState: 'running', effect: { getComputedTiming: () => ({ endTime: Infinity }) }
    } as unknown as Animation])
    expect(isMotionSettled(dialog)).toBe(true)
  })
})
