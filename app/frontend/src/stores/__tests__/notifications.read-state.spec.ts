import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { useNotificationStore } from '@/stores/notifications'
import type { CanonicalNotificationEvent } from '@/types/events'

const api = vi.hoisted(() => ({ getState: vi.fn(), markRead: vi.fn(), clear: vi.fn() }))
vi.mock('@/services/api', () => ({ notificationApi: api }))
const earlier = '2026-10-09T10:00:00.000Z'
const watermark = '2026-10-09T14:00:00.000Z'
const newer = '2026-10-09T16:00:00.000Z'
function event(id: string, created_at = earlier): CanonicalNotificationEvent {
  return { event_id: id, dedupe_key: id, type: 'stream.online', severity: 'info', source: 'test',
    title: id, body: 'Synthetic local history', created_at, actions: [], data: {}, target_url: '/streamers' }
}
function fresh() {
  setActivePinia(createPinia())
  const store = useNotificationStore()
  store.load()
  return store
}
function state(timestamp: string | null) {
  api.getState.mockResolvedValue({ last_read_timestamp: timestamp, last_cleared_timestamp: null, unread_count: 0 })
}
function reads(store: ReturnType<typeof fresh>) {
  return Object.fromEntries(store.notifications.map(item => [item.id, item.read]))
}

beforeEach(() => {
  localStorage.clear()
  vi.resetAllMocks()
  vi.useFakeTimers()
  vi.setSystemTime(new Date(watermark))
  state(null)
  api.markRead.mockImplementation(async (timestamp: string) => {
    state(timestamp)
    return { success: true, last_read_timestamp: timestamp }
  })
  api.clear.mockResolvedValue({ success: true, last_cleared_timestamp: watermark })
})
afterEach(() => vi.useRealTimers())

describe('local item read state versus global watermark', () => {
  it.each(['A', 'B'])('reading only %s never POSTs a global watermark or reads its sibling after reload/sync', async id => {
    let store = fresh()
    store.addFromEvent(event('B', '2026-10-09T12:00:00.000Z'))
    store.addFromEvent(event('A')) // arrives out of order
    await store.syncBackendState()
    store.markRead(id)
    expect(api.markRead).not.toHaveBeenCalled()
    store = fresh()
    await store.syncBackendState()
    await store.syncBackendState()
    expect(reads(store)).toEqual(id === 'A' ? { B: false, A: true } : { B: true, A: false })
    expect(store.unreadCount).toBe(1)
  })

  it('keeps an explicit unread after global read through new Pinia/storage instances and identical/older state', async () => {
    let store = fresh()
    store.addFromEvent(event('A'))
    store.addFromEvent(event('B', '2026-10-09T12:00:00.000Z'))
    await store.markAllRead()
    expect(api.markRead).toHaveBeenCalledExactlyOnceWith(watermark)
    store.markUnread('A')
    for (const timestamp of [watermark, earlier, watermark]) {
      state(timestamp)
      store = fresh()
      await store.syncBackendState()
      await store.syncBackendState()
      expect(reads(store)).toEqual({ A: false, B: true })
    }
    expect(api.markRead).toHaveBeenCalledTimes(1)
  })

  it('a strictly newer global intent supersedes local unread, not items beyond its cutoff', async () => {
    const store = fresh()
    store.addFromEvent(event('A'))
    store.addFromEvent(event('future', '2026-10-09T18:00:00.000Z'))
    state(watermark)
    await store.syncBackendState()
    store.markUnread('A')
    state(newer)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ future: false, A: true })
    store.markUnread('A')
    state(watermark)
    await store.syncBackendState()
    state(newer)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ future: false, A: false })
  })

  it.each([true, false])('preserves local read=%s and its baseline across dedupe/replay', async read => {
    let store = fresh()
    store.addFromEvent(event('A'))
    state(watermark)
    await store.syncBackendState()
    if (read) { store.markUnread('A'); store.markRead('A') } else store.markUnread('A')
    store.addFromEvent({ ...event('replayed'), dedupe_key: 'A' })
    store = fresh()
    await store.syncBackendState()
    expect(store.totalCount).toBe(1)
    expect(reads(store)).toEqual({ replayed: read })
    expect(api.markRead).not.toHaveBeenCalled()
  })

  it('treats first observed state as the baseline for a local action made before sync', async () => {
    let store = fresh()
    store.addFromEvent(event('A'))
    store.markUnread('A')
    store = fresh()
    state(watermark)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ A: false })
    state(newer)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ A: true })
  })

  it('applies existing global state to legacy storage and late arrivals without overriding a later local action', async () => {
    localStorage.setItem('lastReadTimestamp', String(new Date(earlier).getTime()))
    localStorage.setItem('streamvault_notifications', JSON.stringify([
      { id: 'legacy', timestamp: earlier, message: 'Old format' },
      { id: 'explicit-old', timestamp: earlier, read: false },
    ]))
    const store = fresh()
    state(watermark)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ legacy: true, 'explicit-old': true })
    store.addFromEvent(event('late'))
    await store.syncBackendState()
    expect(reads(store)).toEqual({ legacy: true, 'explicit-old': true, late: true })
    store.markUnread('late')
    await store.syncBackendState()
    expect(store.notifications.find(item => item.id === 'late')?.read).toBe(false)
  })

  it('keeps live items beyond a pending mark-all cutoff unread through reply, reload, sync and replay', async () => {
    let store = fresh()
    store.addFromEvent(event('A'))
    store.addFromEvent(event('future', newer))
    await store.syncBackendState()
    let release!: () => void
    api.markRead.mockImplementationOnce(() => new Promise(resolve => {
      release = () => { state(watermark); resolve({ success: true, last_read_timestamp: watermark }) }
    }))
    const pending = store.markAllRead()
    expect(api.markRead).toHaveBeenCalledExactlyOnceWith(watermark)
    store.addFromEvent(event('live', '2026-10-09T14:00:01.000Z'))
    store.addFromEvent(event('at-cutoff', watermark))
    store.addFromEvent(event('late-old', '2026-10-09T11:00:00.000Z'))
    expect(reads(store)).toEqual({ future: false, live: false, 'at-cutoff': false, A: false, 'late-old': false })
    release()
    expect(await pending).toBe(true)
    for (let replay = 0; replay < 2; replay++) {
      expect(reads(store)).toEqual({ future: false, live: false, 'at-cutoff': true, A: true, 'late-old': true })
      expect(store.unreadCount).toBe(2)
      store = fresh()
      await store.syncBackendState()
      store.addFromEvent(event('live', '2026-10-09T14:00:01.000Z'))
      await store.syncBackendState()
    }
    expect(api.markRead).toHaveBeenCalledTimes(1)
  })

  it('does not report global mark-all success or alter local items when the server rejects it', async () => {
    const store = fresh()
    store.addFromEvent(event('A'))
    api.markRead.mockRejectedValueOnce(new Error('synthetic failure'))
    expect(await store.markAllRead()).toBe(false)
    expect(reads(store)).toEqual({ A: false })
    expect(fresh().unreadCount).toBe(1)
  })

  it('a first global intent after observed empty state overrides an explicit local unread', async () => {
    let store = fresh()
    store.addFromEvent(event('A'))
    await store.syncBackendState()
    store.markUnread('A')
    store = fresh()
    state(watermark)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ A: true })
  })

  it('does not lose a known newer cutoff when legacy storage arrives during an older snapshot', async () => {
    const store = fresh()
    store.addFromEvent(event('A'))
    state(newer)
    await store.syncBackendState()
    store.markUnread('A')
    const stored = JSON.parse(localStorage.getItem('streamvault_notifications')!)
    stored.push({ id: 'legacy-late', type: 'recording.completed', timestamp: watermark, read: false })
    localStorage.setItem('streamvault_notifications', JSON.stringify(stored))
    store.load()
    state(earlier)
    await store.syncBackendState()
    state(newer)
    await store.syncBackendState()
    expect(reads(store)).toEqual({ 'legacy-late': true, A: false })
  })

  it('preserves history on state/clear failure; successful clear affects only notification storage', async () => {
    const store = fresh()
    store.addFromEvent(event('A'))
    localStorage.setItem('streamvault-theme', 'light')
    api.getState.mockRejectedValueOnce(new Error('synthetic offline'))
    expect(await store.syncBackendState()).toBe(false)
    api.clear.mockRejectedValueOnce(new Error('synthetic offline'))
    expect(await store.clearAll()).toBe(false)
    expect(fresh().totalCount).toBe(1)
    expect(await store.clearAll()).toBe(true)
    expect(fresh().totalCount).toBe(0)
    expect(localStorage.getItem('streamvault-theme')).toBe('light')
    expect(api.markRead).not.toHaveBeenCalled()
  })
})
