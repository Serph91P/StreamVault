import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import AppShell from '@/components/AppShell.vue'
import NotificationFeed from '@/components/NotificationFeed.vue'
import { useNotificationStore } from '@/stores/notifications'

const api = vi.hoisted(() => ({ getState: vi.fn(), markRead: vi.fn(), clear: vi.fn() }))
const router = vi.hoisted(() => ({ push: vi.fn() }))
vi.mock('@/services/api', () => ({ notificationApi: api }))
vi.mock('vue-router', () => ({ useRouter: () => router }))
vi.mock('@/composables/useAuth', () => ({ useAuth: () => ({ logout: vi.fn() }) }))
vi.mock('@/composables/usePWA', () => ({ usePWA: () => ({ isOnline: ref(true) }) }))
vi.mock('@/composables/useCategoryImages', () => ({ useCategoryImages: () => ({ getCategoryImage: () => '' }) }))
vi.mock('@/composables/useWebSocket', () => ({ useWebSocket: () => ({ connectionStatus: ref('connected'), reconnectAttempt: ref(0) }) }))
vi.mock('@/composables/useNavigation', () => ({ useNavigation: () => ({ isMobile: ref(true), isDesktop: ref(false), sidebarExpanded: ref(false) }) }))
const mounted: ReturnType<typeof mount>[] = []
async function setup(shell = true) {
  localStorage.setItem('streamvault_notifications', JSON.stringify(['A', 'B'].map((id, index) => ({
    id, event_id: id, dedupe_key: id, type: 'stream.online', severity: 'info', title: id, body: `Notice ${id}`,
    timestamp: `2026-10-09T1${index}:00:00Z`, created_at: `2026-10-09T1${index}:00:00Z`, source: 'test',
    actions: [], data: {}, read: false, target_url: '/streamers',
  }))))
  const pinia = createPinia()
  const wrapper = mount(shell ? AppShell : NotificationFeed, { props: shell ? { showShell: true } : {},
    global: { plugins: [pinia], stubs: { Teleport: true, SidebarNav: true, BottomNav: true,
      BackgroundQueueMonitor: true, ThemeToggle: true, NavigationWrapper: { template: '<main><slot /></main>' } } } })
  mounted.push(wrapper)
  if (shell) await wrapper.get('[aria-label="Open notifications"]').trigger('click')
  await flushPromises()
  return { wrapper, store: useNotificationStore(pinia) }
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  localStorage.clear()
  api.getState.mockResolvedValue({ last_read_timestamp: null, last_cleared_timestamp: null, unread_count: 0 })
  api.markRead.mockResolvedValue({ success: true })
  api.clear.mockResolvedValue({ success: true })
})
afterEach(() => { mounted.splice(0).forEach(wrapper => wrapper.unmount()) })

describe('real shell/feed/item action ownership', () => {
  it('opens without writes, toggles one local item and navigates without advancing the global watermark', async () => {
    const { wrapper, store } = await setup()
    expect(store.unreadCount).toBe(2)
    expect(api.markRead).not.toHaveBeenCalled()
    const item = wrapper.findAll('.notification-item')[0]
    await item.get('[aria-label$=" read"]').trigger('click')
    await flushPromises()
    expect(store.unreadCount).toBe(1)
    await wrapper.get('[aria-label="Mark B unread"]').trigger('click')
    await flushPromises()
    expect(store.unreadCount).toBe(2)
    await wrapper.get('[aria-label="Open notification target for B"]').trigger('click')
    await flushPromises()
    expect(router.push).toHaveBeenCalledExactlyOnceWith('/streamers')
    expect(store.unreadCount).toBe(1)
    expect(api.markRead).not.toHaveBeenCalled()
    expect(api.clear).not.toHaveBeenCalled()
  })

  it.each(['mark', 'clear'])('executes a feed %s intent once rather than again in the parent shell', async action => {
    const { wrapper, store } = await setup()
    const label = action === 'mark' ? 'Mark all notifications read' : 'Clear all notifications'
    await wrapper.get(`.notification-feed [aria-label="${label}"]`).trigger('click')
    await flushPromises()
    expect(action === 'mark' ? api.markRead : api.clear).toHaveBeenCalledTimes(1)
    expect(store.unreadCount).toBe(0)
    expect(store.totalCount).toBe(action === 'mark' ? 2 : 0)
  })

  it('shows a mark-all server error without pretending the history is read', async () => {
    const { wrapper, store } = await setup(false)
    api.markRead.mockRejectedValueOnce(new Error('synthetic failure'))
    await wrapper.get('[aria-label="Mark all notifications read"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('could not be marked read')
    expect(store.unreadCount).toBe(2)
  })

  it('does not send another global mutation while a global action is pending', async () => {
    let finish!: (value: unknown) => void
    api.markRead.mockReturnValue(new Promise(resolve => { finish = resolve }))
    const { wrapper, store } = await setup(false)
    const mark = wrapper.get('[aria-label="Mark all notifications read"]')
    await mark.trigger('click')
    await mark.trigger('click')
    await wrapper.get('[aria-label="Clear all notifications"]').trigger('click')
    expect(api.markRead).toHaveBeenCalledTimes(1)
    expect(api.clear).not.toHaveBeenCalled()
    expect(store.unreadCount).toBe(2)
    finish({ success: true })
    await flushPromises()
    expect(store.unreadCount).toBe(0)
  })
})
