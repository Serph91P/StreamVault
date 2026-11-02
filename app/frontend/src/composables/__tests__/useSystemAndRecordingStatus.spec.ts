import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, onMounted, ref, watch } from 'vue'
import { createPinia, disposePinia, type Pinia } from 'pinia'
import { useSystemAndRecordingStatus } from '../useSystemAndRecordingStatus'
import StreamerList from '@/components/StreamerList.vue'

vi.mock('@/composables/useStreamers', () => ({ useStreamers: () => ({ deleteStreamer: vi.fn() }) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const api = vi.hoisted(() => ({
  getStatus: vi.fn(), getActiveRecordingsStatus: vi.fn(), getStreamersStatus: vi.fn(),
  getStreamsStatus: vi.fn(), getNotificationsStatus: vi.fn(),
}))
vi.mock('@/services/api', () => ({ systemApi: api }))
vi.mock('@/utils/logger', () => ({ logDebug: vi.fn(), logError: vi.fn() }))
const authenticated = ref(true)
const connection = ref('connected')
const handlers = new Map<string, Set<(event: any) => void>>()
vi.mock('@/stores/realtime', () => ({ useRealtimeStore: () => ({
  get connectionStatus() { return connection.value },
  onEvent(type: string, callback: (event: any) => void) {
    if (!handlers.has(type)) handlers.set(type, new Set())
    handlers.get(type)!.add(callback)
    return () => handlers.get(type)?.delete(callback)
  },
}) }))

function deferred() {
  let resolve!: (value: any) => void
  let reject!: (error: Error) => void
  const promise = new Promise<any>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const responses = [
  { system: { active_recordings: 0, total_streamers: 0, live_streamers: 0, timestamp: '2026-11-01' } },
  { active_recordings: [] }, { streamers: [] }, { streams: [] },
  { notification_system: { enabled: false, url_configured: false, active_subscriptions: 0, streamers_with_notifications: 0 }, recent_events: [], timestamp: '2026-11-01' },
]
const methods = Object.values(api)
let pending: ReturnType<typeof deferred>[][]
let pinia: Pinia
let unmounts: Array<() => void>
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await nextTick() }
function mount(duplicate = false, target = pinia) {
  let status!: ReturnType<typeof useSystemAndRecordingStatus>
  const app = createApp(defineComponent({ setup() {
    status = useSystemAndRecordingStatus()
    // Same binding as App.vue; auth itself is not replaced by the status owner.
    if (status.setActive) watch(authenticated, status.setActive, { immediate: true, flush: 'sync' })
    if (duplicate) onMounted(() => { void status.fetchAllStatus() })
    return () => h('div', String(status.activeRecordingsCount.value))
  } }))
  app.use(target)
  app.mount(document.createElement('div'))
  const unmount = () => app.unmount()
  unmounts.push(unmount)
  return { status, unmount }
}
function settle(batch = 0) { pending.forEach((requests, i) => requests[batch]?.resolve(responses[i])) }
function counts(expected: number) { methods.forEach(method => expect(method).toHaveBeenCalledTimes(expected)) }
function subscriberCount() { return [...handlers.values()].reduce((n, set) => n + set.size, 0) }

beforeEach(() => {
  vi.useFakeTimers()
  authenticated.value = true
  connection.value = 'connected'
  handlers.clear()
  pending = methods.map(() => [])
  methods.forEach((method, i) => {
    method.mockReset().mockImplementation(() => {
      const request = deferred(); pending[i].push(request); return request.promise
    })
  })
  pinia = createPinia()
  unmounts = []
})
afterEach(() => {
  unmounts.forEach(fn => fn())
  disposePinia(pinia)
  vi.useRealTimers()
})

describe('shared system status lifecycle', () => {
  it.each([1, 2, 3])('hydrates %i consumers with one initial read per resource', async (number) => {
    const consumers = Array.from({ length: number }, () => mount().status)
    counts(1)
    expect(subscriberCount()).toBe(12)
    expect(vi.getTimerCount()).toBe(1)
    settle(); await flush()
    consumers.forEach(status => expect(status.systemStatus.value).toEqual(responses[0].system))
    handlers.get('active_recordings_update')!.forEach(fn => fn({ data: [{ id: 12 }] }))
    consumers.forEach(status => expect(status.activeRecordingsCount.value).toBe(1))
  })

  it.each(['recording.stopped', 'recording.completed'])('preserves the existing %s payload precedence and effects', async type => {
    const { status } = mount()
    pending[1][0].resolve({ active_recordings: [{ id: 11, streamer_id: 1 }, { id: 12, streamer_id: 1 }, { id: 13, streamer_id: 2 }] })
    pending[2][0].resolve({ streamers: [{ id: 1, is_recording: true }, { id: 2, is_recording: true }] })
    settle(); await flush()
    const emit = (data: unknown) => handlers.get(type)!.forEach(fn => fn({ data }))
    const before = status.lastUpdate.value
    emit(null)
    expect(status.lastUpdate.value).toBe(before)
    emit({ recording_id: 11, streamer_id: 1 })
    expect(status.activeRecordings.value.map(rec => rec.id)).toEqual([12, 13])
    expect(status.streamersStatus.value[0].is_recording).toBe(true)
    expect(status.lastUpdate.value).not.toBe(before)
    emit({ streamer_id: 1 })
    expect(status.activeRecordings.value.map(rec => rec.id)).toEqual([13])
    expect(status.streamersStatus.value.map(s => s.is_recording)).toEqual([false, true])
    emit({ recording_id: 13 })
    expect(status.activeRecordings.value).toEqual([])
    expect(status.streamersStatus.value[1].is_recording).toBe(true)
    counts(1)
    expect(subscriberCount()).toBe(12)
  })

  it('preserves named-streamer event matching, field guards and unmatched-event no-ops', async () => {
    const { status } = mount()
    pending[2][0].resolve({ streamers: [{ id: 1, name: 'one', display_name: 'ONE', is_live: false }, { id: 2, name: 'two', display_name: 'TWO', is_live: false }] })
    settle(); await flush()
    const emit = (type: string, data: unknown) => handlers.get(type)!.forEach(fn => fn({ data }))
    emit('channel.update', { streamer_name: 'ONE', title: 'fresh', category_name: 'games', language: 'de' })
    expect(status.streamersStatus.value[0]).toMatchObject({ current_title: 'fresh', current_category: 'games', language: 'de' })
    emit('channel.update', { streamer_name: 'one', title: '', category_name: '', language: '' })
    expect(status.streamersStatus.value[0]).toMatchObject({ current_title: 'fresh', current_category: 'games', language: 'de' })
    emit('stream.online', { streamer_name: 'one' })
    expect(status.streamersStatus.value[0].is_live).toBe(true)
    expect(status.streamersStatus.value[0].last_seen).toBeTruthy()
    emit('stream.offline', { streamer_name: 'ONE' })
    expect(status.streamersStatus.value[0]).toMatchObject({ is_live: false, current_title: null, current_category: null })
    const before = status.lastUpdate.value
    for (const type of ['channel.update', 'stream.online', 'stream.offline']) {
      emit(type, null)
      emit(type, { streamer_name: 'absent', title: 'ignored' })
    }
    expect(status.lastUpdate.value).toBe(before)
    expect(status.streamersStatus.value[1]).toEqual({ id: 2, name: 'two', display_name: 'TWO', is_live: false })
    counts(1)
    expect(subscriberCount()).toBe(12)
  })

  it('coalesces the old App mounted fetch with initial hydration', async () => {
    const { status } = mount(true)
    counts(1)
    settle(); await flush()
    expect(status.isLoading.value).toBe(false)
    expect(status.error.value).toBeNull()
  })

  it('keeps loading until the final mixed result and preserves errors across later successes', async () => {
    const { status } = mount()
    pending[0][0].resolve(responses[0]); await flush()
    expect(status.isLoading.value).toBe(true)
    pending[1][0].reject(new Error('recordings unavailable')); await flush()
    pending[2][0].resolve(responses[2]); pending[3][0].resolve(responses[3]); await flush()
    expect(status.isLoading.value).toBe(true)
    expect(status.error.value).toContain('recordings unavailable')
    pending[4][0].resolve(responses[4]); await flush()
    expect(status.isLoading.value).toBe(false)
    expect(status.error.value).toContain('recordings unavailable')
    expect(status.streamersStatus.value).toEqual([])
  })

  it('retains last successful data on failure, distinguishes stale from empty and retries freshly', async () => {
    const { status } = mount()
    pending[1][0].resolve({ active_recordings: [{ id: 12 }] }); settle(); await flush()
    const refresh = status.forceRefresh()
    counts(2)
    pending[1][1].reject(new Error('temporary failure')); settle(1); await refresh
    expect(status.activeRecordings.value).toEqual([{ id: 12 }])
    expect(status.error.value).toContain('temporary failure')

    const again = status.forceRefresh()
    counts(3)
    settle(2); await again
    expect(status.activeRecordings.value).toEqual([])
    expect(status.error.value).toBeNull()
    methods.forEach(method => expect(method.mock.calls[2][0]).toHaveProperty('t'))
  })

  it('queues one delayed reconnect refresh behind in-flight hydration', async () => {
    mount(); mount(); mount()
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    counts(1)
    settle(); await flush()
    counts(2)
    settle(1); await flush()
    await vi.advanceTimersByTimeAsync(180000)
    counts(2)
  })

  it('coalesces concurrent force refreshes waiting for the same in-flight batch', async () => {
    const a = mount().status; const b = mount().status; const c = mount().status
    const refreshes = [a.forceRefresh(), b.forceRefresh(), c.forceRefresh()]
    counts(1)
    settle(); await flush()
    counts(2)
    settle(1); await Promise.all(refreshes)
    counts(2)
    expect(a.systemStatus.value).toEqual(responses[0].system)
    expect(b.systemStatus.value).toEqual(responses[0].system)
    expect(c.systemStatus.value).toEqual(responses[0].system)
  })

  it('owns one emergency fallback only after the offline threshold', async () => {
    mount(); mount(); mount()
    settle(); await flush()
    connection.value = 'offline'; await nextTick()
    await vi.advanceTimersByTimeAsync(120000)
    counts(1)
    await vi.advanceTimersByTimeAsync(60000)
    counts(2)
    settle(1); await flush()
  })

  it('keeps the owner alive for another consumer and tears down the last consumer', async () => {
    const a = mount(); const b = mount()
    a.unmount(); unmounts.shift()
    expect(subscriberCount()).toBe(12)
    settle(); await flush()
    handlers.get('active_recordings_update')!.forEach(fn => fn({ data: [{ id: 12 }] }))
    expect(b.status.activeRecordingsCount.value).toBe(1)
    b.unmount(); unmounts.shift()
    expect(subscriberCount()).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    await vi.advanceTimersByTimeAsync(200000)
    counts(1)
  })

  it('resets on logout and ignores old results after a new authenticated generation', async () => {
    const { status } = mount()
    const queuedRefresh = status.forceRefresh()
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    authenticated.value = false; await nextTick()
    expect(status.isLoading.value).toBe(false)
    expect(subscriberCount()).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    authenticated.value = true; await nextTick()
    counts(2)
    settle(1); await flush()
    pending[0][0].resolve({ system: { ...responses[0].system, total_streamers: 999 } })
    settle(); await flush()
    await queuedRefresh
    counts(2)
    expect(status.systemStatus.value?.total_streamers).toBe(0)
    expect(status.isLoading.value).toBe(false)
  })

  it('does not fetch private status on the visible unauthenticated lifecycle', async () => {
    authenticated.value = false
    const { status } = mount(true)
    await flush()
    counts(0)
    expect(subscriberCount()).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    expect(status.systemStatus.value).toBeNull()
  })

  it('leaves reconnect hydration to the owner when the real StreamerList is mounted', async () => {
    const app = createApp(defineComponent({ setup() {
      const status = useSystemAndRecordingStatus()
      status.setActive(true)
      return () => h(StreamerList)
    } }))
    app.use(pinia)
    app.mount(document.createElement('div'))
    unmounts.push(() => app.unmount())
    settle(); await flush()
    counts(1)
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    counts(1)
    await vi.advanceTimersByTimeAsync(1000)
    counts(2)
    settle(1); await flush()
  })

  it('keeps reconnect ownership after the first consumer unmounts', async () => {
    const first = mount(); mount()
    settle(); await flush()
    first.unmount(); unmounts.shift()
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    await vi.advanceTimersByTimeAsync(1000)
    counts(2)
    settle(1); await flush()
  })

  it('disposes subscriptions, timers and pending results with the Pinia owner', async () => {
    const { status } = mount()
    connection.value = 'offline'; await nextTick()
    connection.value = 'connected'; await nextTick()
    disposePinia(pinia)
    expect(subscriberCount()).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    settle(); await flush()
    expect(status.systemStatus.value).toBeNull()
    status.setActive(false)
    status.setActive(true)
    expect(subscriberCount()).toBe(0)
    expect(vi.getTimerCount()).toBe(0)
    counts(1)
  })

  it('does not share status across separate Pinia app owners', async () => {
    const otherPinia = createPinia()
    const a = mount().status
    const b = mount(false, otherPinia).status
    counts(2)
    pending[0][0].resolve(responses[0])
    pending[0][1].resolve({ system: { ...responses[0].system, total_streamers: 7 } })
    await flush()
    expect(a.systemStatus.value?.total_streamers).toBe(0)
    expect(b.systemStatus.value?.total_streamers).toBe(7)
    disposePinia(otherPinia)
  })
})
