import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BackgroundQueueMonitor from '../BackgroundQueueMonitor.vue'

const { forceRefreshFromAPI, queueState } = vi.hoisted(() => ({
  forceRefreshFromAPI: vi.fn(),
  queueState: {
    queueStats: { __v_isRef: true as const, value: { total_tasks: 0, completed_tasks: 0, failed_tasks: 0, pending_tasks: 0 } },
    activeTasks: { __v_isRef: true as const, value: [] as any[] },
    recentTasks: { __v_isRef: true as const, value: [] as any[] },
    isLoading: { __v_isRef: true as const, value: false },
    connectionStatus: 'connected',
  },
}))

vi.mock('@/composables/useBackgroundQueue', () => ({
  useBackgroundQueue: () => ({
    ...queueState,
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
    vi.clearAllMocks()
    queueState.queueStats.value = { total_tasks: 0, completed_tasks: 0, failed_tasks: 0, pending_tasks: 0 }
    queueState.activeTasks.value = []
    queueState.recentTasks.value = []
    queueState.isLoading.value = false
    queueState.connectionStatus = 'connected'
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

  it('renders the connected empty state', async () => {
    const wrapper = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await wrapper.get('button').trigger('click')
    await flushFocus()
    expect(document.body.textContent).toContain('No background tasks running')
    wrapper.unmount()
  })

  it('renders loading, retryable disconnect, and progress states', async () => {
    queueState.isLoading.value = true
    const loading = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await loading.get('button').trigger('click')
    expect(document.querySelector('[role="status"]')?.textContent).toContain('Loading background jobs')
    loading.unmount()

    queueState.isLoading.value = false
    queueState.connectionStatus = 'error'
    const disconnected = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await disconnected.get('button').trigger('click')
    const alert = document.querySelector<HTMLElement>('[role="alert"]')
    expect(alert?.textContent).toContain('updates are unavailable')
    const refreshCallsBeforeRetry = forceRefreshFromAPI.mock.calls.length
    alert?.querySelector<HTMLButtonElement>('button')?.click()
    await nextTick()
    expect(forceRefreshFromAPI).toHaveBeenCalledTimes(refreshCallsBeforeRetry + 1)
    disconnected.unmount()

    queueState.connectionStatus = 'connected'
    queueState.activeTasks.value = [{
      id: 'task-1', task_type: 'thumbnail', status: 'running', progress: 73,
      started_at: '2026-10-09T12:00:00Z', payload: { streamer_name: 'Alpha' },
    }]
    const active = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await active.get('button').trigger('click')
    expect(document.querySelector('.progress-text')?.textContent).toBe('73%')
    active.unmount()
  })
})
