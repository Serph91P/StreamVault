import { nextTick, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia } from 'pinia'

const { stats, task, api } = vi.hoisted(() => {
  const stats = { total_tasks: 1, completed_tasks: 0, failed_tasks: 0, retried_tasks: 0, pending_tasks: 1, active_tasks: 1, workers: 1, is_running: true }
  const task = { id: 'queue-1', task_type: 'recording', status: 'running', progress: 25, created_at: '2026-01-01T00:00:00Z', retry_count: 0, payload: { streamer_name: 'Fixture Streamer', stream_id: 1, recording_id: 1 } }
  const api = { getStats: vi.fn(async () => stats), getActiveTasks: vi.fn(async () => [task]), getRecentTasks: vi.fn(async () => []) }
  return { stats, task, api }
})

// Keep the production realtime Pinia store. Mock only its external manager.
vi.mock('@/composables/useWebSocket', async () => {
  const { ref } = await vi.importActual<typeof import('vue')>('vue')
  const manager = {
    connectionStatus: ref('disconnected'),
    messages: ref([]),
    isBrowserOnline: ref(true),
    reconnectAttempt: ref(0),
    maxReconnectAttemptCount: 5,
    subscribe: vi.fn(() => vi.fn()),
    onMessage: vi.fn(),
    reconnectNow: vi.fn(),
  }
  return { WebSocketManager: { getInstance: () => manager } }
})
vi.mock('@/services/api', () => ({ backgroundQueueApi: api }))
vi.mock('@/composables/useSystemAndRecordingStatus', () => ({ useSystemAndRecordingStatus: () => ({ activeRecordings: ref([]) }) }))
vi.mock('@/composables/useModal', () => ({ useModal: () => {
  const isOpen = ref(false)
  return { isOpen, open: () => { isOpen.value = true }, close: () => { isOpen.value = false } }
} }))

import BackgroundQueueMonitor from '@/components/BackgroundQueueMonitor.vue'
import { useRealtimeStore } from '@/stores/realtime'
import { useBackgroundQueueStore } from '@/stores/backgroundQueue'
import { WebSocketManager } from '@/composables/useWebSocket'

const manager = WebSocketManager.getInstance()
const wrappers: ReturnType<typeof mount>[] = []

async function openPanel(pinia: ReturnType<typeof createPinia>) {
  const wrapper = mount(BackgroundQueueMonitor, { global: { plugins: [pinia] } })
  wrappers.push(wrapper)
  await flushPromises()
  await wrapper.get('.queue-status-indicator').trigger('click')
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  manager.connectionStatus.value = 'disconnected'
  api.getStats.mockResolvedValue(stats)
  api.getActiveTasks.mockResolvedValue([task])
  api.getRecentTasks.mockResolvedValue([])
})

afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  // Teleported dialogs must not leak into the next test's assertions.
  document.body.replaceChildren()
})

describe('production BackgroundQueueMonitor + composable + both Pinia stores', () => {
  it('CONTROL: connected-at-mount renders statistics with the real Pinia-unwrapped string', async () => {
    const pinia = createPinia()
    manager.connectionStatus.value = 'connected'
    const realtime = useRealtimeStore(pinia)
    expect(realtime.connectionStatus).toBe('connected')
    await openPanel(pinia)
    expect(document.body.textContent ?? '').toContain('Total:')
    expect(document.body.textContent ?? '').not.toContain('Background queue updates are unavailable.')
  })

  it('REGRESSION: updates an already-open panel when realtime changes disconnected -> connected', async () => {
    const pinia = createPinia()
    const realtime = useRealtimeStore(pinia)
    const queue = useBackgroundQueueStore(pinia)
    api.getStats.mockRejectedValue(new Error('Synthetic initial REST unavailable'))
    await openPanel(pinia)
    expect(document.body.textContent ?? '').toContain('Background queue updates are unavailable.')
    manager.connectionStatus.value = 'connected'
    // Feed a synthetic message through the real realtime store's dispatcher,
    // so REST fallback alone cannot accidentally satisfy the recovery test.
    const dispatch = vi.mocked(manager.onMessage).mock.calls[0]![0]
    dispatch({ type: 'background_queue_update', data: { stats, active_tasks: [task], recent_tasks: [] } })
    await nextTick()
    expect(realtime.connectionStatus).toBe('connected')
    expect(queue.queueStats.total_tasks).toBe(1)
    expect(queue.activeTasks.map(task => task.id)).toEqual(['queue-1'])
    expect(document.body.textContent ?? '').not.toContain('Background queue updates are unavailable.')
    expect(document.body.textContent ?? '').toContain('Total:')
  })

  it('REGRESSION: shows successful REST retry data even while realtime remains disconnected', async () => {
    const pinia = createPinia()
    const queue = useBackgroundQueueStore(pinia)
    await openPanel(pinia)
    vi.clearAllMocks()
    const retry = document.body.querySelector<HTMLButtonElement>('button.glass-btn-text')!
    retry.click()
    await flushPromises()
    expect(api.getStats).toHaveBeenCalledTimes(1)
    expect(api.getActiveTasks).toHaveBeenCalledTimes(1)
    expect(api.getRecentTasks).toHaveBeenCalledTimes(1)
    // Verify real store data before checking the failing display contract.
    expect(queue.queueStats.total_tasks).toBe(1)
    expect(queue.activeTasks.map(task => task.id)).toEqual(['queue-1'])
    expect(queue.error).toBeNull()
    expect(document.body.textContent ?? '').not.toContain('Background queue updates are unavailable.')
    expect(document.body.textContent ?? '').toContain('Total:')
  })

  it('preserves empty, single-task, and mixed-task progress averages', () => {
    const queue = useBackgroundQueueStore(createPinia())
    expect(queue.totalProgress).toBe(0)
    queue.setActiveTasks([{ ...task, status: 'running' }])
    expect(queue.totalProgress).toBe(25)
    queue.setActiveTasks([{ ...task, status: 'running' }, { ...task, id: 'queue-2', status: 'running', progress: 75 }])
    expect(queue.totalProgress).toBe(50)
    queue.setActiveTasks([])
    expect(queue.totalProgress).toBe(0)
  })

  it('escapes genuine API error text instead of interpreting markup', async () => {
    const message = '<img src=x onerror="alert(1)"> Synthetic queue error'
    api.getStats.mockRejectedValue(new Error(message))
    await openPanel(createPinia())
    expect(document.body.textContent).toContain(message)
    expect(document.body.querySelector('[role="alert"] img')).toBeNull()
  })

  it('CONTROL: a genuine synthetic REST failure remains an error, not successful data', async () => {
    const pinia = createPinia()
    const queue = useBackgroundQueueStore(pinia)
    api.getStats.mockRejectedValue(new Error('Synthetic queue HTTP failure'))
    await openPanel(pinia)
    expect(queue.hasError).toBe(true)
    expect(queue.error).toBe('Synthetic queue HTTP failure')
    expect(document.body.textContent ?? '').toContain('Background queue updates are unavailable.')
    expect(document.body.textContent ?? '').toContain('Synthetic queue HTTP failure')
    expect(document.body.textContent ?? '').not.toContain('Total:')
  })
})
