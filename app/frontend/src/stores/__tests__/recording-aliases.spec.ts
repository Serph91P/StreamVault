import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS, type RealtimeEvent } from '@/types/events'
import { useRealtimeStore } from '@/stores/realtime'
import { useRecordingStore } from '@/stores/recordings'

// Only the external manager delivery seam is synthetic; both Pinia stores are real.
const transport = vi.hoisted(() => ({ deliver: (_event: RealtimeEvent<string>) => {} }))
vi.mock('@/composables/useWebSocket', () => ({ WebSocketManager: { getInstance: () => ({
  subscribe: () => {}, onMessage: (callback: typeof transport.deliver) => { transport.deliver = callback },
  connectionStatus: ref('connected'), messages: ref([]), isBrowserOnline: ref(true),
  reconnectAttempt: ref(0), maxReconnectAttemptCount: 5, reconnectNow: () => {}
}) } }))

const pairs = Object.entries(CANONICAL_REALTIME_EVENT_TYPE_BY_ALIAS).filter(([alias]) => alias.startsWith('recording_'))
const recording = { id: 71, streamer_id: 7, stream_id: 17, streamer_name: 'Synthetic', title: 'Fixture', started_at: '2026-01-01T00:00:00Z', status: 'recording', duration: 0, file_path: '/synthetic/71.mp4' }

beforeEach(() => setActivePinia(createPinia()))
afterEach(() => vi.restoreAllMocks())

describe.each(pairs)('%s / %s dispatch', (legacy, canonical) => {
  it.each([legacy, canonical])('delivers %s once to each logical callback without rewriting the envelope', type => {
    const realtime = useRealtimeStore()
    const same = vi.fn(), other = vi.fn()
    realtime.onEvent(legacy, same)
    realtime.onEvent(canonical, same)
    realtime.onEvents([legacy, canonical, legacy], other)
    const event = Object.freeze({ type, event_id: 91, cursor: 'epoch:91', timestamp: 123, data: Object.freeze({ recording_id: 71 }) })
    transport.deliver(event)
    expect(same).toHaveBeenCalledExactlyOnceWith(event)
    expect(other).toHaveBeenCalledExactlyOnceWith(event)
    expect(same.mock.calls[0][0]).toBe(event)
    expect(event.type).toBe(type)
  })

  it.each([legacy, canonical])('retains independently registered ownership after partial unsubscribe for %s', type => {
    const realtime = useRealtimeStore()
    const callback = vi.fn()
    const offLegacy = realtime.onEvent(legacy, callback)
    const offCanonical = realtime.onEvent(canonical, callback)
    offLegacy(); offLegacy()
    transport.deliver({ type })
    expect(callback).toHaveBeenCalledTimes(1)
    offCanonical(); offCanonical()
    transport.deliver({ type })
    expect(callback).toHaveBeenCalledTimes(1)
  })
})

it('onEvents duplicate aliases release only their own registrations, idempotently', () => {
  const realtime = useRealtimeStore(), callback = vi.fn()
  const off = realtime.onEvents(['recording_started', 'recording.started', 'recording_started'], callback)
  const remaining = realtime.onEvent('recording_started', callback)
  transport.deliver({ type: 'recording.started' })
  expect(callback).toHaveBeenCalledTimes(1)
  off(); off()
  transport.deliver({ type: 'recording_started' })
  expect(callback).toHaveBeenCalledTimes(2)
  remaining(); remaining()
  transport.deliver({ type: 'recording.started' })
  expect(callback).toHaveBeenCalledTimes(2)
})

it('preserves unknown and non-aliased types and does not merge separately delivered event IDs', () => {
  const realtime = useRealtimeStore()
  for (const type of ['future.recording', 'active_recordings_update', 'streamer_online']) {
    const callback = vi.fn()
    realtime.onEvent(type, callback)
    transport.deliver({ type, event_id: 1 })
    transport.deliver({ type, event_id: 2 })
    expect(callback.mock.calls.map(([event]) => event.event_id)).toEqual([1, 2])
  }
})

for (const mode of ['direct', 'bound'] as const) {
  describe.each(pairs)(`${mode} reducer %s / %s`, (legacy, canonical) => {
    it.each([legacy, canonical])('preserves existing recording/DOM effects for %s', type => {
      const store = useRecordingStore()
      store.setActiveRecordings([recording])
      const completed = vi.fn(), available = vi.fn()
      window.addEventListener('recording_completed', completed)
      window.addEventListener('recording_available', available)
      const off = mode === 'bound' ? store.bindRealtime() : () => {}
      const event = { type, data: { ...recording, recording_id: 71, status: 'completed', recording_path: '/synthetic/71.mp4' } }
      if (mode === 'direct') store.applyRealtimeEvent(event)
      else transport.deliver(event)
      if (['recording_stopped', 'recording_status_update', 'recording_completed'].includes(legacy)) {
        expect(store.activeRecordings).toEqual([])
      } else {
        expect(store.activeRecordings.map(item => item.id)).toEqual([71])
      }
      if (legacy === 'recording_started') {
        expect(store.activeRecordings[0].status).toBe('completed')
      }
      expect(completed).toHaveBeenCalledTimes(legacy === 'recording_completed' ? 1 : 0)
      expect(available).toHaveBeenCalledTimes(legacy === 'recording_available' ? 1 : 0)
      if (legacy === 'recording_completed') expect((completed.mock.calls[0][0] as CustomEvent).detail).toEqual({ recording_id: 71, file_path: '/synthetic/71.mp4', stream_id: 17 })
      if (legacy === 'recording_available') expect((available.mock.calls[0][0] as CustomEvent).detail).toEqual({ stream_id: 17, recording_path: '/synthetic/71.mp4', streamer_id: 7, streamer_name: 'Synthetic', title: 'Fixture' })
      off()
      window.removeEventListener('recording_completed', completed)
      window.removeEventListener('recording_available', available)
    })
  })
}

it.each(['recording_started', 'recording.started'])('adds an absent recording for %s', type => {
  const store = useRecordingStore()
  store.applyRealtimeEvent({ type, data: { ...recording, recording_id: 71 } })
  expect(store.activeRecordings).toEqual([{ ...recording, recording_id: 71 }])
})

it.each(['recording_status_update', 'recording.status_update'])('keeps active status and removes each terminal status for %s', type => {
  const store = useRecordingStore()
  for (const status of ['recording', 'completed', 'failed', 'stopped', 'cancelled']) {
    store.setActiveRecordings([recording])
    store.applyRealtimeEvent({ type, data: { streamer_id: 7, status } })
    expect(store.activeRecordingsCount).toBe(status === 'recording' ? 1 : 0)
  }
})

it('multiple recording consumers share one binding and each disposer is idempotent', () => {
  const store = useRecordingStore()
  const completed = vi.fn()
  window.addEventListener('recording_completed', completed)
  const first = store.bindRealtime(), second = store.bindRealtime()
  const event = { type: 'recording_completed', data: { recording_id: 71 } }
  transport.deliver(event)
  expect(completed).toHaveBeenCalledTimes(1)
  first(); first()
  transport.deliver(event)
  expect(completed).toHaveBeenCalledTimes(2)
  second(); second()
  transport.deliver(event)
  expect(completed).toHaveBeenCalledTimes(2)
  const rebound = store.bindRealtime()
  transport.deliver(event)
  expect(completed).toHaveBeenCalledTimes(3)
  rebound()
  window.removeEventListener('recording_completed', completed)
})
