import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SurfaceCard from '../SurfaceCard.vue'
import surfaceCardSource from '../SurfaceCard.vue?raw'

function keydown(key: 'Enter' | ' ') {
  return new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
}

describe('SurfaceCard', () => {
  it('owns an opaque semantic panel rather than delegating to GlassCard', () => {
    const wrapper = mount(SurfaceCard, { slots: { title: 'Owned surface', default: 'Content' } })

    expect(wrapper.classes()).toContain('surface-card')
    expect(wrapper.find('.surface-card-body').text()).toContain('Content')
    expect(surfaceCardSource).not.toContain("GlassCard from")
    expect(surfaceCardSource).not.toContain('<GlassCard')
    expect(surfaceCardSource).toMatch(/background:\s*var\(--sv-cmp-panel-background\);/)
    expect(surfaceCardSource).toMatch(/backdrop-filter:\s*none;/)
  })

  it('activates its own enabled clickable surface once per Enter and Space', () => {
    const wrapper = mount(SurfaceCard, { props: { clickable: true } })

    for (const key of ['Enter', ' '] as const) {
      const event = keydown(key)
      expect(wrapper.element.dispatchEvent(event)).toBe(false)
      expect(event.defaultPrevented).toBe(true)
    }

    expect(wrapper.attributes('role')).toBe('button')
    expect(wrapper.attributes('tabindex')).toBe('0')
    expect(wrapper.emitted('click')).toHaveLength(2)
  })

  it.each([
    ['disabled', { clickable: true, disabled: true }],
    ['loading', { clickable: true, loading: true }],
    ['nonclickable', {}],
  ])('does not activate or prevent keys when the surface is %s', (_state, props) => {
    const wrapper = mount(SurfaceCard, { props })

    for (const key of ['Enter', ' '] as const) {
      const event = keydown(key)
      expect(wrapper.element.dispatchEvent(event)).toBe(true)
      expect(event.defaultPrevented).toBe(false)
    }

    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it.each([
    ['link', '<a href="/streamer/1/stream/1/watch">Watch</a>'],
    ['button', '<button type="button">Watch</button>'],
    ['input', '<input aria-label="Watch" />'],
  ])('leaves Enter and Space on a descendant %s native for clickable and nonclickable surfaces', (_name, content) => {
    for (const props of [{ clickable: true }, { clickable: false }]) {
      const wrapper = mount(SurfaceCard, { props, slots: { default: content } })
      const control = wrapper.get('a, button, input')

      for (const key of ['Enter', ' '] as const) {
        const event = keydown(key)
        expect(control.element.dispatchEvent(event)).toBe(true)
        expect(event.defaultPrevented).toBe(false)
      }

      expect(wrapper.emitted('click')).toBeUndefined()
    }
  })

  it('keeps mouse activation limited to enabled clickable surfaces', () => {
    const active = mount(SurfaceCard, { props: { clickable: true } })
    const disabled = mount(SurfaceCard, { props: { clickable: true, disabled: true } })

    active.trigger('click')
    disabled.trigger('click')

    expect(active.emitted('click')).toHaveLength(1)
    expect(disabled.emitted('click')).toBeUndefined()
  })
})
