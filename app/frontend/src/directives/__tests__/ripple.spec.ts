import { defineComponent, h, withDirectives } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ripple from '../ripple'

const RippleHarness = defineComponent({
  setup() {
    return () => withDirectives(h('button', { type: 'button' }, 'Ripple target'), [[ripple]])
  },
})

function mountRipple() {
  return mount(RippleHarness, { attachTo: document.body })
}

describe('ripple directive motion and cleanup', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('never vibrates on activation', async () => {
    const vibrate = vi.fn()
    vi.stubGlobal('navigator', { vibrate })
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
    const wrapper = mountRipple()

    await wrapper.get('button').trigger('click', { clientX: 10, clientY: 10 })
    wrapper.unmount()

    expect(vibrate).not.toHaveBeenCalled()
  })

  it('does not animate a ripple when reduced motion is preferred', async () => {
    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })))
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
    const wrapper = mountRipple()

    await wrapper.get('button').trigger('click', { clientX: 10, clientY: 10 })
    const rippleCount = wrapper.findAll('.ripple-effect-element').length
    wrapper.unmount()

    expect(rippleCount).toBe(0)
  })

  it('does not create a ripple for touch movement without a confirmed click', () => {
    const wrapper = mountRipple()
    const button = wrapper.get('button').element

    button.dispatchEvent(new Event('touchstart', { bubbles: true }))
    button.dispatchEvent(new Event('touchmove', { bubbles: true }))
    button.dispatchEvent(new Event('touchend', { bubbles: true }))

    expect(button.querySelectorAll('.ripple-effect-element')).toHaveLength(0)
    wrapper.unmount()
  })

  it('removes owned timers, listeners, and ripple nodes on unmount', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
    const wrapper = mountRipple()
    const button = wrapper.get('button').element

    button.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 10, clientY: 10 }))
    expect(button.querySelectorAll('.ripple-effect-element')).toHaveLength(1)

    wrapper.unmount()
    button.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 10, clientY: 10 }))

    expect({
      pendingTimers: vi.getTimerCount(),
      rippleNodes: button.querySelectorAll('.ripple-effect-element').length,
    }).toEqual({ pendingTimers: 0, rippleNodes: 0 })
  })

  it('does not let a queued animation frame mutate nodes after cleanup', () => {
    let frameCallback: FrameRequestCallback | undefined
    const cancelAnimationFrame = vi.fn()
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => {
      frameCallback = callback
      return 17
    }))
    vi.stubGlobal('cancelAnimationFrame', cancelAnimationFrame)
    const wrapper = mountRipple()
    const button = wrapper.get('button').element

    button.dispatchEvent(new MouseEvent('click', { bubbles: true, clientX: 10, clientY: 10 }))
    wrapper.unmount()
    frameCallback?.(0)

    expect(cancelAnimationFrame).toHaveBeenCalledWith(17)
    expect(button.querySelectorAll('.ripple-effect-element')).toHaveLength(0)
  })
})
