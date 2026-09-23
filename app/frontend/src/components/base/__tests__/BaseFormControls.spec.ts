import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import BaseDropdown from '../BaseDropdown.vue'
import BaseInput from '../BaseInput.vue'

describe('BaseInput', () => {
  it('uses a native labelled input and links its error description', () => {
    const wrapper = mount(BaseInput, {
      props: {
        id: 'stream-url',
        modelValue: '',
        label: 'Stream URL',
        error: 'Enter a valid URL',
        required: true,
      },
    })

    const input = wrapper.get('input')
    expect(wrapper.get('label').attributes('for')).toBe('stream-url')
    expect(input.attributes('id')).toBe('stream-url')
    expect(input.attributes('required')).toBeDefined()
    expect(input.attributes('aria-invalid')).toBe('true')
    expect(input.attributes('aria-describedby')).toBe('stream-url-error')
    expect(wrapper.get('#stream-url-error').text()).toBe('Enter a valid URL')
  })

  it('keeps external descriptions and uses native disabled semantics', async () => {
    const wrapper = mount(BaseInput, {
      attrs: { 'aria-describedby': 'format-help' },
      props: { id: 'proxy-url', modelValue: 'https://example.test', hint: 'HTTPS only', disabled: true },
    })
    const input = wrapper.get('input')

    expect(input.attributes('aria-describedby')).toBe('format-help proxy-url-hint')
    expect((input.element as HTMLInputElement).disabled).toBe(true)
    expect(input.classes()).toContain('base-form-control-target')
    await input.trigger('input')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})

describe('BaseDropdown', () => {
  it('uses a native labelled select and links its error description', () => {
    const wrapper = mount(BaseDropdown, {
      props: {
        id: 'quality',
        modelValue: '',
        label: 'Quality',
        placeholder: 'Choose a quality',
        options: [{ label: 'Source', value: 'source' }],
        error: 'Choose a quality',
        required: true,
      },
    })

    const select = wrapper.get('select')
    expect(wrapper.get('label').attributes('for')).toBe('quality')
    expect(select.attributes('id')).toBe('quality')
    expect(select.attributes('required')).toBeDefined()
    expect(select.attributes('aria-invalid')).toBe('true')
    expect(select.attributes('aria-describedby')).toBe('quality-error')
    expect(wrapper.get('#quality-error').text()).toBe('Choose a quality')
  })

  it('uses the form-control target contract and native disabled behavior', async () => {
    const wrapper = mount(BaseDropdown, {
      props: {
        id: 'streamer',
        modelValue: 'one',
        options: [{ label: 'One', value: 'one' }],
        disabled: true,
      },
    })
    const select = wrapper.get('select')

    expect((select.element as HTMLSelectElement).disabled).toBe(true)
    expect(select.classes()).toContain('base-form-control-target')
    await select.trigger('change')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })
})
