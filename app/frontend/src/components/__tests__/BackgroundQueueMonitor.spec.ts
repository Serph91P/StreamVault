import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BackgroundQueueMonitor from '../BackgroundQueueMonitor.vue'

const { forceRefreshFromAPI } = vi.hoisted(() => ({
  forceRefreshFromAPI: vi.fn(),
}))

vi.mock('@/composables/useBackgroundQueue', () => ({
  useBackgroundQueue: () => ({
    queueStats: { value: { total_tasks: 0, completed_tasks: 0, failed_tasks: 0, pending_tasks: 0 } },
    activeTasks: { value: [] },
    recentTasks: { value: [] },
    isLoading: { value: false },
    connectionStatus: 'connected',
    forceRefreshFromAPI,
    cancelStreamTasks: vi.fn(),
  }),
}))

vi.mock('@/composables/useSystemAndRecordingStatus', () => ({
  useSystemAndRecordingStatus: () => ({ activeRecordings: { value: [] } }),
}))

async function flushFocus() {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
}

describe('BackgroundQueueMonitor', () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.body.style.cssText = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('focuses the dialog on open, closes with Escape, and restores its trigger', async () => {
    const wrapper = mount(BackgroundQueueMonitor, { attachTo: document.body })
    const trigger = wrapper.get('button')

    trigger.element.focus()
    await trigger.trigger('click')
    await flushFocus()
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')
    expect(dialog?.contains(document.activeElement)).toBe(true)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()

    expect(document.querySelector('[role="dialog"]')).toBeNull()
    expect(document.activeElement).toBe(trigger.element)
    wrapper.unmount()
  })

  it('uses unique dialog and title ids for independent queue entry points', async () => {
    const wrapper = mount(defineComponent({
      render: () => h('div', [h(BackgroundQueueMonitor), h(BackgroundQueueMonitor)]),
    }), { attachTo: document.body })
    const triggers = wrapper.findAll('button')

    await triggers[0].trigger('click')
    await triggers[1].trigger('click')

    const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'))
    const ids = dialogs.map((dialog) => dialog.id)
    const titleIds = dialogs.map((dialog) => dialog.getAttribute('aria-labelledby'))
    expect(new Set(ids).size).toBe(2)
    expect(new Set(titleIds).size).toBe(2)
    wrapper.unmount()
  })
})
