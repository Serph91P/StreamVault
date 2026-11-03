import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useBackgroundQueueStore, type BackgroundQueueTask } from '../backgroundQueue'
import { backgroundQueueApi } from '@/services/api'

vi.mock('@/stores/realtime', () => ({
  useRealtimeStore: () => ({ connectionStatus: 'connected' })
}))
vi.mock('@/services/api', () => ({
  backgroundQueueApi: {
    getStats: vi.fn(),
    getActiveTasks: vi.fn(),
    getRecentTasks: vi.fn()
  }
}))

describe('background queue initial hydration', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(backgroundQueueApi.getStats).mockResolvedValue({ total_tasks: 1 } as never)
    vi.mocked(backgroundQueueApi.getActiveTasks).mockResolvedValue([{ id: 'existing-task', progress: 40 }] as never)
    vi.mocked(backgroundQueueApi.getRecentTasks).mockResolvedValue([])
  })

  it('hydrates a monitor mounted after the socket connected, only once', async () => {
    const store = useBackgroundQueueStore()
    await store.hydrateWhenDisconnected()
    expect(store.dataAvailable).toBe(true)
    expect(store.activeTasks[0]?.id).toBe('existing-task')
    await store.hydrateWhenDisconnected()
    expect(backgroundQueueApi.getStats).toHaveBeenCalledTimes(1)
  })

  it('coalesces initial hydration for concurrently mounted monitors', async () => {
    const store = useBackgroundQueueStore()
    await Promise.all([store.hydrateWhenDisconnected(), store.hydrateWhenDisconnected()])
    expect(backgroundQueueApi.getStats).toHaveBeenCalledTimes(1)
  })

  it.each(['completed', 'failed'] as const)('keeps one recent row for repeated %s task snapshots', (status) => {
    const store = useBackgroundQueueStore()
    const task: BackgroundQueueTask = {
      id: 'same-task', task_type: 'acceptance', status, progress: 99,
      created_at: '2026-01-01T00:00:00Z', retry_count: 0,
      payload: { streamer_name: 'Synthetic acceptance', stream_id: 933, recording_id: 933 }
    }
    store.applyTaskStatusUpdate(task)
    store.applyTaskStatusUpdate({ ...task, progress: 100 })
    expect(store.recentTasks).toHaveLength(1)
    expect(store.recentTasks[0].progress).toBe(100)
  })
})
