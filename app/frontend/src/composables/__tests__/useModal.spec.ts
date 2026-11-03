import { defineComponent, h, nextTick, ref, Teleport } from 'vue'
import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useModal } from '../useModal'

interface ModalHarnessVm {
  isOpen: boolean
  open: () => void
  close: () => void
}

const ModalHarness = defineComponent({
  props: {
    name: { type: String, required: true },
    autoFocus: { type: Boolean, default: true },
  },
  setup(props, { expose }) {
    const dialog = ref<HTMLElement | null>(null)
    const closed = ref(0)
    const modal = useModal(dialog, { autoFocus: props.autoFocus, onClose: () => { closed.value += 1 } })
    expose({ ...modal, closed })

    return () => modal.isOpen.value
      ? h('div', { ref: dialog, role: 'dialog', tabindex: -1 }, [
          h('button', `${props.name} first`),
          h('button', `${props.name} last`),
        ])
      : null
  },
})

async function flushFocus() {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
}

describe('useModal', () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.body.style.cssText = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('keeps the body locked until the final stacked modal closes', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    const first = mount(ModalHarness, { props: { name: 'first' }, attachTo: document.body })
    const second = mount(ModalHarness, { props: { name: 'second' }, attachTo: document.body })
    const firstVm = first.vm as unknown as ModalHarnessVm
    const secondVm = second.vm as unknown as ModalHarnessVm

    firstVm.open()
    secondVm.open()
    await flushFocus()
    const secondControl = second.get('button').element
    firstVm.close()

    expect(document.body.style.overflow).toBe('hidden')
    expect(document.activeElement).toBe(secondControl)

    secondVm.close()
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(trigger)
    first.unmount()
    second.unmount()
  })

  it('owns one document listener for the full overlay stack lifecycle', () => {
    const first = mount(ModalHarness, { props: { name: 'first' }, attachTo: document.body })
    const second = mount(ModalHarness, { props: { name: 'second' }, attachTo: document.body })
    const firstVm = first.vm as unknown as ModalHarnessVm
    const secondVm = second.vm as unknown as ModalHarnessVm
    const addListener = vi.spyOn(document, 'addEventListener')
    const removeListener = vi.spyOn(document, 'removeEventListener')

    firstVm.open()
    secondVm.open()
    secondVm.close()

    expect(document.body.style.overflow).toBe('hidden')
    expect(removeListener).not.toHaveBeenCalled()

    firstVm.close()
    expect(addListener).toHaveBeenCalledTimes(1)
    expect(addListener).toHaveBeenCalledWith('keydown', expect.any(Function))
    expect(removeListener).toHaveBeenCalledTimes(1)
    expect(removeListener).toHaveBeenCalledWith('keydown', expect.any(Function))
    first.unmount()
    second.unmount()
  })

  it('lets Escape close only the topmost modal and restores focus in stack order', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    const first = mount(ModalHarness, { props: { name: 'first' }, attachTo: document.body })
    const second = mount(ModalHarness, { props: { name: 'second' }, attachTo: document.body })
    const firstVm = first.vm as unknown as ModalHarnessVm
    const secondVm = second.vm as unknown as ModalHarnessVm

    firstVm.open()
    await flushFocus()
    const firstControl = first.get('button').element
    secondVm.open()
    await flushFocus()

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()

    expect(secondVm.isOpen).toBe(false)
    expect(firstVm.isOpen).toBe(true)
    expect(document.activeElement).toBe(firstControl)
    expect(document.body.style.overflow).toBe('hidden')

    firstVm.close()
    expect(document.activeElement).toBe(trigger)
    first.unmount()
    second.unmount()
  })

  it.each([false, true])('autofocus respects eligibility and falls back to the dialog when empty=%s', async empty => {
    const Harness = defineComponent({
      setup(_, { expose }) {
        const dialog = ref<HTMLElement | null>(null)
        const modal = useModal(dialog)
        expose(modal)
        return () => modal.isOpen.value ? h('div', { ref: dialog, role: 'dialog', tabindex: -1 }, [
          h('button', { tabindex: -1 }, 'negative'),
          h('fieldset', { disabled: true }, [h('button', 'inherited disabled')]),
          ...(!empty ? [h('button', { id: 'eligible' }, 'eligible')] : []),
        ]) : null
      },
    })
    const wrapper = mount(Harness, { attachTo: document.body })
    const vm = wrapper.vm as unknown as ModalHarnessVm
    try {
      vm.open()
      await flushFocus()
      expect(document.activeElement).toBe(wrapper.get(empty ? '[role="dialog"]' : '#eligible').element)
    } finally {
      vm.close()
      wrapper.unmount()
    }
  })

  it('preserves only the topmost separate backdrop and restores prior isolation on close', async () => {
    const Harness = defineComponent({
      setup(_, { expose }) {
        const dialog = ref<HTMLElement | null>(null)
        const backdrop = ref<HTMLElement | null>(null)
        const modal = useModal(dialog, { backdrop })
        expose(modal)
        return () => modal.isOpen.value ? h(Teleport, { to: 'body' }, [
          h('div', { ref: backdrop, class: 'backdrop', 'aria-hidden': 'true' }),
          h('div', { ref: dialog, role: 'dialog', tabindex: -1 }, [h('button', 'Close')]),
        ]) : null
      },
    })
    const background = document.createElement('main')
    background.setAttribute('aria-hidden', 'false')
    document.body.append(background)
    const first = mount(Harness, { attachTo: document.body })
    const second = mount(Harness, { attachTo: document.body })
    const firstVm = first.vm as unknown as ModalHarnessVm
    const secondVm = second.vm as unknown as ModalHarnessVm
    try {
      firstVm.open()
      await flushFocus()
      const firstBackdrop = document.querySelector<HTMLElement>('.backdrop')!
      const firstDialog = document.querySelector<HTMLElement>('[role="dialog"]')!
      expect(firstBackdrop.inert).not.toBe(true)
      expect(firstBackdrop.getAttribute('aria-hidden')).toBe('true')
      expect(background.inert).toBe(true)
      secondVm.open()
      await flushFocus()
      const secondBackdrop = document.querySelectorAll<HTMLElement>('.backdrop')[1]!
      expect(secondBackdrop.inert).not.toBe(true)
      expect(firstBackdrop.inert).toBe(true)
      expect(firstDialog.inert).toBe(true)
      secondVm.close()
      await flushFocus()
      expect(firstBackdrop.inert).not.toBe(true)
      expect(background.inert).toBe(true)
      firstVm.close()
      expect(background.inert).not.toBe(true)
      expect(background.getAttribute('aria-hidden')).toBe('false')
      expect(firstBackdrop.getAttribute('aria-hidden')).toBe('true')
    } finally {
      second.unmount()
      first.unmount()
    }
  })

  it('isolates without autofocus and releases isolation and body lock on unmount', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    const wrapper = mount(ModalHarness, { props: { name: 'manual focus', autoFocus: false }, attachTo: document.body })
    const vm = wrapper.vm as unknown as ModalHarnessVm
    vm.open()
    await flushFocus()
    expect(wrapper.get('[role="dialog"]').element.contains(document.activeElement)).toBe(false)
    expect(trigger.inert).toBe(true)
    expect(document.body.style.overflow).toBe('hidden')
    wrapper.unmount()
    await flushFocus()
    expect(trigger.inert).not.toBe(true)
    expect(trigger.hasAttribute('aria-hidden')).toBe(false)
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(trigger)
    // Closing an already unmounted/closed owner must remain a no-op.
    vm.close()
    expect(document.body.style.overflow).toBe('')
  })

  it('wraps forward and backward Tab when focus escapes during modal hydration', async () => {
    const outside = document.createElement('button')
    document.body.append(outside)
    const wrapper = mount(ModalHarness, { props: { name: 'hydrating' }, attachTo: document.body })
    const vm = wrapper.vm as unknown as ModalHarnessVm

    vm.open()
    await flushFocus()
    const controls = wrapper.findAll('button').map(button => button.element)

    outside.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }))
    expect(document.activeElement).toBe(controls[0])

    outside.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }))
    expect(document.activeElement).toBe(controls[1])

    vm.close()
    wrapper.unmount()
    outside.remove()
  })
})
