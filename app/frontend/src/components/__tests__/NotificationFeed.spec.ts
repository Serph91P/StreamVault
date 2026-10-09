import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { StoredNotification } from '@/services/notificationStorage'

const api = vi.hoisted(() => ({
  clear: vi.fn(),
  getState: vi.fn(),
  markRead: vi.fn(),
}))
const router = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('@/services/api', () => ({ notificationApi: api }))
vi.mock('vue-router', () => ({ useRouter: () => router }))

import NotificationFeed from '@/components/NotificationFeed.vue'
import { useNotificationStore } from '@/stores/notifications'

const first: StoredNotification = {
  id: 'first', event_id: 'first', dedupe_key: 'first', type: 'stream.online', severity: 'info',
  title: 'First', body: 'first notification', timestamp: '2026-10-09T12:00:00Z',
  created_at: '2026-10-09T12:00:00Z', source: 'websocket', actions: [], data: {}, read: false,
}
const second: StoredNotification = {
  ...first, id: 'second', event_id: 'second', dedupe_key: 'second', type: 'recording.failed',
  severity: 'error', title: 'Second', timestamp: '2026-10-09T13:00:00Z', read: true,
}

function mountFeed() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mount(NotificationFeed, {
    global: {
      plugins: [pinia],
      stubs: {
        NotificationFilters: { template: '<button data-testid="unread" @click="$emit(\'update:modelValue\', \'unread\')">Unread</button>' },
        NotificationItem: { template: '<article>{{ notification.title }}</article>', props: ['notification'] },
        NotificationState: { template: '<section :data-state="state"><button v-if="actionLabel" @click="$emit(\'action\')">{{ actionLabel }}</button></section>', props: ['state', 'actionLabel'] },
      },
    },
  })
  return { wrapper, store: useNotificationStore(pinia) }
}

describe('NotificationFeed states', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    api.getState.mockResolvedValue({})
    api.clear.mockResolvedValue({})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps local items available after backend-sync failure and retries the state sync', async () => {
    localStorage.setItem('streamvault_notifications', JSON.stringify([first]))
    api.getState.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({})
    const { wrapper, store } = mountFeed()

    await flushPromises()
    expect(wrapper.get('[data-state="error"]').text()).toContain('Retry')
    expect(store.totalCount).toBe(1)

    await wrapper.get('[data-state="error"] button').trigger('click')
    await flushPromises()
    expect(api.getState).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-state="error"]').exists()).toBe(false)
    expect(store.totalCount).toBe(1)
  })

  it('filters unread notifications and clears local state only after the clear action', async () => {
    const { wrapper, store } = mountFeed()
    store.notifications = [first, second]
    await flushPromises()

    await wrapper.get('[data-testid="unread"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('First')
    expect(wrapper.text()).not.toContain('Second')

    await wrapper.get('[aria-label="Clear all notifications"]').trigger('click')
    await flushPromises()
    expect(api.clear).toHaveBeenCalledOnce()
    expect(store.totalCount).toBe(0)
    expect(wrapper.emitted('clear-all')).toHaveLength(1)
  })
})
