import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BaseModal from '../BaseModal.vue'
import BaseSheet from '../BaseSheet.vue'

describe('BaseModal', () => {
  it.each([BaseModal, BaseSheet])('names the shared dismiss control in the product language', async Component => {
    const wrapper = mount(Component, { props: { modelValue: true, title: 'Vorgaben prüfen' }, attachTo: document.body })
    try {
      const button = document.querySelector('[role="dialog"] button')!
      expect(button.getAttribute('aria-label')).toBe('Dialog schließen')
    } finally { wrapper.unmount() }
  })
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.body.style.cssText = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('does not release a stacked modal body lock when another modal closes', async () => {
    const first = mount(BaseModal, {
      props: { modelValue: true, title: 'First' },
      attachTo: document.body,
    })
    const second = mount(BaseModal, {
      props: { modelValue: true, title: 'Second' },
      attachTo: document.body,
    })

    await first.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('hidden')

    await second.setProps({ modelValue: false })
    expect(document.body.style.overflow).toBe('')
    first.unmount()
    second.unmount()
  })

  it('reacts to closeOnEsc changes while open', async () => {
    const wrapper = mount(BaseModal, {
      props: { modelValue: true, title: 'Dynamic Escape', closeOnEsc: false },
      attachTo: document.body,
    })

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.setProps({ closeOnEsc: true })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
    wrapper.unmount()
  })
})
