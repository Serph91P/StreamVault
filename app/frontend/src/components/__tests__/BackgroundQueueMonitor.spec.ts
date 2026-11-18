import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BackgroundQueueMonitor from '../BackgroundQueueMonitor.vue'

const { forceRefreshFromAPI, queueState, recordingState } = await vi.hoisted(async () => {
  const { ref } = await import('vue')
  return {
    forceRefreshFromAPI: vi.fn(),
    recordingState: { activeRecordings: ref<Array<{ id: number; status: string; streamer_name: string }>>([]), snapshotsStale: ref(false) },
    queueState: {
      queueStats: ref({ total_tasks: 0, completed_tasks: 0, failed_tasks: 0, pending_tasks: 0 }),
      activeTasks: ref<any[]>([]),
      recentTasks: ref<any[]>([]),
      isLoading: ref(false),
      connectionStatus: ref('connected'),
      dataAvailable: ref(false),
      error: ref<string | null>(null),
    },
  }
})

vi.mock('@/composables/useBackgroundQueue', () => ({
  useBackgroundQueue: () => ({
    ...queueState,
    forceRefreshFromAPI,
    cancelStreamTasks: vi.fn(),
  }),
}))

vi.mock('@/composables/useSystemAndRecordingStatus', () => ({
  useSystemAndRecordingStatus: () => recordingState,
}))

async function flushFocus() {
  await nextTick()
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
}

describe('BackgroundQueueMonitor', () => {
  it('links its short preview to the complete activity without changing queue truth', async () => {
    queueState.recentTasks.value = Array.from({ length: 12 }, (_, id) => ({ id, task_type: 'thumbnail', status: 'completed' }))
    const wrapper = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await wrapper.get('button').trigger('click')
    const dialog = document.querySelector('[role="dialog"]')!
    expect(dialog.querySelector('router-link')?.getAttribute('to')).toBe('/activity')
    expect(dialog.querySelectorAll('.recent-tasks-section .task-item')).toHaveLength(3)
    expect(queueState.recentTasks.value).toHaveLength(12)
    wrapper.unmount()
  })
  beforeEach(() => {
    vi.clearAllMocks()
    queueState.queueStats.value = { total_tasks: 0, completed_tasks: 0, failed_tasks: 0, pending_tasks: 0 }
    queueState.activeTasks.value = []
    queueState.recentTasks.value = []
    queueState.isLoading.value = false
    queueState.connectionStatus.value = 'connected'
    queueState.dataAvailable.value = true
    vi.spyOn(HTMLElement.prototype, 'offsetParent', 'get').mockReturnValue(document.body)
    recordingState.activeRecordings.value = []
    recordingState.snapshotsStale.value = false
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.body.style.cssText = ''
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it.each([0, 1, 2])('includes the visible Queue count in the accessible name for %i jobs', count => {
    queueState.activeTasks.value = Array.from({ length: count }, (_, id) => ({
      id: `task-${id}`, task_type: 'thumbnail', status: 'running', progress: 50,
      started_at: '2026-10-09T12:00:00Z', payload: { streamer_name: 'Synthetic' },
    }))
    const wrapper = mount(BackgroundQueueMonitor)
    const trigger = wrapper.get('.queue-status-indicator')
    try {
      expect(trigger.attributes('aria-label')).toContain(`Queue ${count}`)
      expect(wrapper.get('.queue-info').text()).toBe(`Queue ${count}`)
      expect(trigger.attributes('aria-label')).toContain(`${count} active ${count === 1 ? 'job' : 'jobs'}`)
    } finally {
      wrapper.unmount()
    }
  })

  it.each([0, 1])('does not certify cached recordings with %i fresh queue tasks, and restores the combined header after repair', async count => {
    recordingState.activeRecordings.value = [{ id: 987, status: 'recording', streamer_name: 'Last known' }]
    queueState.activeTasks.value = Array.from({ length: count }, (_, id) => ({
      id: `task-${id}`, task_type: 'thumbnail', status: 'running', progress: 50,
    }))
    const wrapper = mount(BackgroundQueueMonitor)
    try {
      const trigger = wrapper.get('.queue-status-indicator')
      expect(trigger.attributes('aria-expanded')).toBe('false')
      expect(wrapper.get('.queue-count').text()).toBe(String(count + 1))
      expect(trigger.find('.progress-bar').exists()).toBe(true)
      recordingState.snapshotsStale.value = true
      await nextTick()
      expect(trigger.attributes('aria-label')).toMatch(/unavailable|outdated|last-known|stale/i)
      expect(trigger.text()).toMatch(/unavailable|outdated|last-known|stale/i)
      expect(wrapper.get('.queue-count').text()).toBe('?')
      expect(trigger.find('.progress-bar').exists()).toBe(false)
      expect(recordingState.activeRecordings.value).toHaveLength(1)
      expect(queueState.activeTasks.value).toHaveLength(count)
      recordingState.snapshotsStale.value = false
      await nextTick()
      expect(trigger.attributes('aria-label')).toContain(`${count + 1} active`)
      expect(wrapper.get('.queue-count').text()).toBe(String(count + 1))
      expect(trigger.find('.progress-bar').exists()).toBe(true)
    } finally {
      wrapper.unmount()
    }
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
    queueState.connectionStatus.value = 'error'
    queueState.dataAvailable.value = false
    const disconnected = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await disconnected.get('button').trigger('click')
    const alert = document.querySelector<HTMLElement>('[role="alert"]')
    expect(alert?.textContent).toContain('updates are unavailable')
    const refreshCallsBeforeRetry = forceRefreshFromAPI.mock.calls.length
    alert?.querySelector<HTMLButtonElement>('button')?.click()
    await nextTick()
    expect(forceRefreshFromAPI).toHaveBeenCalledTimes(refreshCallsBeforeRetry + 1)
    disconnected.unmount()

    queueState.connectionStatus.value = 'connected'
    queueState.activeTasks.value = [{
      id: 'task-1', task_type: 'thumbnail', status: 'running', progress: 73,
      started_at: '2026-10-09T12:00:00Z', payload: { streamer_name: 'Alpha' },
    }]
    queueState.dataAvailable.value = true
    const active = mount(BackgroundQueueMonitor, { attachTo: document.body })
    await active.get('button').trigger('click')
    expect(document.querySelector('.progress-text')?.textContent).toBe('73%')
    active.unmount()
  })
})
