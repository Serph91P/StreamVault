import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BaseDropdown from '../BaseDropdown.vue'
import BaseSheet from '../BaseSheet.vue'

describe('foundation primitive behavior', () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('focuses an already-open sheet and restores focus after Escape', async () => {
    const launcher = document.createElement('button')
    document.body.append(launcher)
    launcher.focus()
    const wrapper = mount(BaseSheet, {
      props: { modelValue: true, title: 'Filters' },
      slots: { default: '<button data-first>Apply</button>' },
      attachTo: document.body,
    })

    await new Promise(resolve => requestAnimationFrame(resolve))
    expect(document.querySelector('.base-sheet')?.contains(document.activeElement)).toBe(true)
    expect(document.activeElement?.matches('button')).toBe(true)

    document.activeElement?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    await wrapper.setProps({ modelValue: false })
    expect(document.activeElement).toBe(launcher)
    wrapper.unmount()
  })

  it('preserves numeric option values in native dropdown events', async () => {
    const wrapper = mount(BaseDropdown, {
      props: {
        modelValue: 10,
        options: [
          { label: 'Ten', value: 10 },
          { label: 'Twenty', value: 20 },
        ],
      },
    })

    await wrapper.get('select').setValue('20')
    expect(wrapper.emitted('update:modelValue')).toEqual([[20]])
    expect(wrapper.emitted('change')).toEqual([[20]])
  })
})
