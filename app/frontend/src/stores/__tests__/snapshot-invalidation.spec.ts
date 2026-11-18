import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'

vi.mock('@/router', () => ({ default: { afterEach: vi.fn(), push: vi.fn(async () => {}) } }))
const api = vi.hoisted(() => ({ getStats: vi.fn(), getActiveTasks: vi.fn(), getRecentTasks: vi.fn() }))
vi.mock('@/services/api', () => ({ backgroundQueueApi: api }))

class Socket {
  static OPEN = 1
  static CONNECTING = 0
  static instances: Socket[] = []
  readyState = 0
  onopen?: () => void
  onmessage?: (event: { data: string }) => void
  onclose?: (event: { code: number; reason: string }) => void
  constructor() { Socket.instances.push(this) }
  open() { this.readyState = 1; this.onopen?.() }
  message(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }) }
  close() { this.readyState = 3; this.onclose?.({ code: 1000, reason: 'synthetic disconnect' }) }
}
const task = (id: string, progress = 10) => ({ id, task_type: 'remux', status: 'running', progress,
  created_at: '2026-01-01T00:00:00Z', retry_count: 0,
  payload: { streamer_name: id, stream_id: 1, recording_id: 1 } })
const stats = { total_tasks: 2, completed_tasks: 0, failed_tasks: 0, retried_tasks: 0,
  pending_tasks: 0, active_tasks: 1, workers: 1, is_running: true }
const snapshot = (id: string) => ({ type: 'background_queue_update', data: { stats, active_tasks: [task(id)], recent_tasks: [] } })
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
let pinia: ReturnType<typeof createPinia>
let replay: ReturnType<typeof deferred<Response>>

beforeEach(() => {
  vi.resetModules()
  vi.resetAllMocks()
  vi.useFakeTimers()
  vi.stubEnv('VITE_USE_MOCK_DATA', 'false')
  vi.stubGlobal('WebSocket', Socket)
  Socket.instances = []
  window.history.replaceState({}, '', '/')
  replay = deferred<Response>()
  vi.stubGlobal('fetch', vi.fn(() => replay.promise))
  api.getStats.mockResolvedValue(stats)
  api.getActiveTasks.mockResolvedValue([task('fresh-task')])
  api.getRecentTasks.mockResolvedValue([])
  pinia = createPinia()
  setActivePinia(pinia)
})
afterEach(() => { disposePinia(pinia); vi.clearAllTimers(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.unstubAllEnvs() })

async function setup() {
  const { WebSocketManager } = await import('@/composables/useWebSocket')
  const { useBackgroundQueueStore } = await import('../backgroundQueue')
  const queue = useBackgroundQueueStore()
  const off = queue.bindRealtime()
  const manager = WebSocketManager.getInstance()
  const received: number[] = []
  manager.onMessage(e => { if (typeof e.event_id === 'number') received.push(e.event_id) })
  const first = Socket.instances[0]!
  first.open()
  first.message({ type: 'connection.status', data: { generation: 'old' } })
  first.message({ ...snapshot('stale-task'), event_id: 100 })
  expect(queue.dataAvailable).toBe(true)
  return { queue, manager, received, off, first }
}
async function reconnect(manager: { reconnectNow: () => void }, first: Socket, reset: boolean, events: unknown[] = []) {
  first.close()
  manager.reconnectNow()
  const second = Socket.instances[1]!
  second.open()
  const id = reset ? 1 : 103
  second.message({ type: 'test', event_id: id, data: {} })
  replay.resolve(new Response(JSON.stringify({ events: [{ type: 'test', event_id: id, data: {} }, ...events],
    reset, gap: !reset, generation: reset ? 'new' : 'old', latest_event_id: id,
    oldest_event_id: id, retained_events: events.length + 1, max_retained_events: 500 })))
  await flushPromises()
  return second
}

describe('snapshot repair through the real manager, replay and Pinia dispatch', () => {
  it('does not certify a partial queue message while an authoritative repair is pending', async () => {
    const { queue, manager, first } = await setup()
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    const second = await reconnect(manager, first, false)
    second.message({ type: 'background_queue_update', event_id: 104, data: { stats } })
    active.resolve([task('fresh-task')])
    await flushPromises()
    expect(queue.dataAvailable).toBe(false)
  })

  it('reloads cached data after the last subscriber detached and missed ordinary live updates', async () => {
    const { queue, first, off } = await setup()
    off()
    first.message({ ...snapshot('missed-while-detached'), event_id: 101 })
    const release = queue.bindRealtime()
    await queue.hydrateWhenDisconnected()
    expect(queue.activeTasks[0]?.id).toBe('fresh-task')
    expect(api.getStats).toHaveBeenCalledTimes(1)
    release()
  })

  it('invalidates an unbound cached store and renews it when a consumer remounts', async () => {
    const { queue, manager, first, off } = await setup()
    off()
    await reconnect(manager, first, true)
    expect(queue.dataAvailable).toBe(false)
    expect(api.getStats).not.toHaveBeenCalled()
    const release = queue.bindRealtime()
    await queue.hydrateWhenDisconnected()
    expect(queue.activeTasks[0]?.id).toBe('fresh-task')
    expect(api.getStats).toHaveBeenCalledTimes(1)
    release()
  })

  it('starts a post-gap read after the pre-gap request finishes instead of accepting its stale result', async () => {
    const { queue, manager, first } = await setup()
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    const beforeGap = queue.forceRefreshFromAPI()
    await reconnect(manager, first, false)
    expect(queue.dataAvailable).toBe(false)
    active.resolve([task('pre-gap-read')])
    await beforeGap
    await flushPromises()
    expect(queue.activeTasks[0]?.id).toBe('fresh-task')
    expect(api.getStats).toHaveBeenCalledTimes(2)
  })


  it.each([true, false])('renews an already available stale queue after reset=%s without a retained queue snapshot', async reset => {
    const { queue, manager, received, first } = await setup()
    const second = await reconnect(manager, first, reset)
    second.message({ type: 'test', event_id: reset ? 2 : 103, data: {} })
    expect(queue.activeTasks.map(t => t.id)).toEqual(['fresh-task'])
    expect(queue.dataAvailable).toBe(true)
    expect(api.getStats).toHaveBeenCalledTimes(1)
    expect(received).toEqual(reset ? [100, 1, 2] : [100, 103])
  })

  it('marks failed repair unavailable, retains last-known data and supports an explicit retry', async () => {
    const { queue, manager, first } = await setup()
    api.getStats.mockRejectedValueOnce(new Error('Synthetic HTTP 503'))
    await reconnect(manager, first, false)
    expect(queue.dataAvailable).toBe(false)
    expect(queue.activeTasks[0]?.id).toBe('stale-task')
    expect(queue.error).toBe('Synthetic HTTP 503')
    await queue.forceRefreshFromAPI()
    expect(queue.dataAvailable).toBe(true)
    expect(queue.activeTasks[0]?.id).toBe('fresh-task')
    expect(api.getStats).toHaveBeenCalledTimes(2)
  })

  it('does not certify a retained pre-gap snapshot as a current server read', async () => {
    const { queue, manager, first } = await setup()
    api.getStats.mockRejectedValueOnce(new Error('Synthetic HTTP 503'))
    await reconnect(manager, first, false, [{ ...snapshot('retained-stale-task'), event_id: 104 }])
    expect(queue.dataAvailable).toBe(false)
    expect(queue.error).toBe('Synthetic HTTP 503')
  })

  it('coalesces concurrent refreshes and does not overwrite a newer complete live snapshot', async () => {
    const { queue, first } = await setup()
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    const one = queue.forceRefreshFromAPI()
    const two = queue.forceRefreshFromAPI()
    first.message({ ...snapshot('new-live-task'), event_id: 101 })
    active.resolve([task('slow-old-task')])
    await Promise.all([one, two])
    expect(queue.activeTasks[0]?.id).toBe('new-live-task')
    expect(queue.dataAvailable).toBe(true)
    expect(api.getStats).toHaveBeenCalledTimes(1)
  })

  it('does not overwrite a live task delta with an older HTTP response', async () => {
    const { queue, first } = await setup()
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    const reading = queue.forceRefreshFromAPI()
    first.message({ type: 'task_progress_update', event_id: 101, data: { task_id: 'stale-task', progress: 90 } })
    active.resolve([task('stale-task', 20)])
    await reading
    expect(queue.activeTasks[0]?.progress).toBe(90)
  })

  it('keeps another binding alive after duplicate release, and stops detached read effects', async () => {
    const { queue, first, off } = await setup()
    const secondOff = queue.bindRealtime()
    off(); off()
    first.message({ ...snapshot('still-bound'), event_id: 101 })
    expect(queue.activeTasks[0]?.id).toBe('still-bound')
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    const reading = queue.forceRefreshFromAPI()
    secondOff()
    active.resolve([task('detached-read')])
    await reading
    expect(queue.activeTasks[0]?.id).toBe('still-bound')
  })

  it('does not apply pending repair after Pinia disposal', async () => {
    const { queue, manager, first } = await setup()
    const active = deferred<ReturnType<typeof task>[]>()
    api.getActiveTasks.mockReturnValueOnce(active.promise)
    await reconnect(manager, first, true)
    expect(api.getActiveTasks).toHaveBeenCalledTimes(1)
    disposePinia(pinia)
    active.resolve([task('disposed-read')])
    await flushPromises()
    expect(queue.activeTasks[0]?.id).toBe('stale-task')
  })
})
