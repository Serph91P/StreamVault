import { defineComponent, h, nextTick, ref } from 'vue'
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
  },
  setup(props, { expose }) {
    const dialog = ref<HTMLElement | null>(null)
    const closed = ref(0)
    const modal = useModal(dialog, { onClose: () => { closed.value += 1 } })
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
})
