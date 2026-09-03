import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BaseButton from '../BaseButton.vue'

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
})
