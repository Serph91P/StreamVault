import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SurfaceCard from '../SurfaceCard.vue'
import surfaceCardSource from '../SurfaceCard.vue?raw'

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

  it('keeps native activation and disabled semantics for interactive surfaces', async () => {
    const wrapper = mount(SurfaceCard, { props: { clickable: true } })
    await wrapper.trigger('keydown.enter')
    await wrapper.trigger('keydown.space')

    expect(wrapper.attributes('role')).toBe('button')
    expect(wrapper.attributes('tabindex')).toBe('0')
    expect(wrapper.emitted('click')).toHaveLength(2)

    await wrapper.setProps({ disabled: true })
    expect(wrapper.attributes('aria-disabled')).toBe('true')
    expect(wrapper.attributes('tabindex')).toBeUndefined()
  })
})
