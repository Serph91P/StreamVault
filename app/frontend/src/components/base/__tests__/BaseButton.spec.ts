import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BaseButton from '../BaseButton.vue'
import BaseIconButton from '../BaseIconButton.vue'

describe('BaseButton', () => {
  it('uses a native button type by default and emits clicks', async () => {
    const wrapper = mount(BaseButton, { slots: { default: 'Save' } })

    expect(wrapper.get('button').attributes('type')).toBe('button')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('is inaccessible to clicks while loading and exposes its busy label', async () => {
    const wrapper = mount(BaseButton, {
      props: { loading: true, loadingLabel: 'Saving' },
      slots: { default: 'Save' },
    })
    const button = wrapper.get('button')

    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    expect(button.attributes('aria-busy')).toBe('true')
    expect(button.attributes('aria-label')).toBe('Saving')
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })

  it('maps ordinary and primary buttons to the documented 44px and 48px target contracts', () => {
    const ordinary = mount(BaseButton, {
      props: { variant: 'secondary' },
      slots: { default: 'Cancel' },
    })
    const primary = mount(BaseButton, {
      props: { variant: 'primary' },
      slots: { default: 'Save' },
    })

    expect(ordinary.get('button').classes()).toContain('base-button-target--ordinary')
    expect(primary.get('button').classes()).toContain('base-button-target--primary')
  })
})

describe('BaseIconButton', () => {
  it('renders a labelled native button and emits clicks', async () => {
    const wrapper = mount(BaseIconButton, {
      props: { label: 'Open actions' },
      slots: { default: '<svg data-test="icon" />' },
    })
    const button = wrapper.get('button')

    expect(button.attributes('type')).toBe('button')
    expect(button.attributes('aria-label')).toBe('Open actions')
    expect(button.classes()).toContain('base-icon-button-target--icon')
    expect(button.find('[data-test="icon"]').exists()).toBe(true)
    await button.trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })

  it('uses native disabled semantics and suppresses clicks', async () => {
    const wrapper = mount(BaseIconButton, {
      props: { label: 'Open actions', disabled: true },
    })
    const button = wrapper.get('button')

    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeUndefined()
  })
})
