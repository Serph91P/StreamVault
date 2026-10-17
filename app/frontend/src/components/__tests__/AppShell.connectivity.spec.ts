import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { h, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AppShell from '../AppShell.vue'
import shellSource from '../AppShell.vue?raw'
import { useNotificationStore } from '@/stores/notifications'

const connection = vi.hoisted(() => ({ reconnectNow: vi.fn() }))
const status = ref('connected')
const online = ref(true)
const attempt = ref(2)
vi.mock('@/composables/useAuth', () => ({ useAuth: () => ({ logout: vi.fn() }) }))
vi.mock('@/composables/usePWA', () => ({ usePWA: () => ({ isOnline: online }) }))
vi.mock('@/composables/useWebSocket', () => ({ useWebSocket: () => ({
  connectionStatus: status, reconnectAttempt: attempt, maxReconnectAttempts: 5, reconnectNow: connection.reconnectNow
}) }))
vi.mock('@/composables/useNavigation', () => ({ useNavigation: () => ({
  isMobile: ref(true), isDesktop: ref(false), sidebarExpanded: ref(false)
}) }))

const mounted: ReturnType<typeof mount>[] = []
afterEach(() => { mounted.forEach(w => w.unmount()); mounted.length = 0; status.value = 'connected'; online.value = true; attempt.value = 2 })

describe('Shell connectivity layout ownership (jsdom, not physical geometry)', () => {
  it('keeps visible truthful status and retry in content flow before usable page controls', async () => {
    const pinia = createPinia()
    const store = useNotificationStore(pinia) // Real reactive Pinia shape, no ref-valued fake store fields.
    const back = vi.fn()
    const wrapper = mount(AppShell, {
      props: { showShell: true },
      slots: { default: () => h('button', { class: 'page-back', onClick: back }, 'Back') },
      global: { plugins: [pinia], mocks: { back }, stubs: {
        SidebarNav: true, BottomNav: true, BackgroundQueueMonitor: true, ThemeToggle: true, NotificationFeed: true
      } }
    })
    mounted.push(wrapper)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.find('.main-content .page-back').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Open notifications"]').exists()).toBe(true)
    expect(store.unreadCount).toBe(0)
    status.value = 'failed'
    await nextTick()
    const main = wrapper.get('.main-content')
    const banner = main.get('[role="status"]')
    expect(banner.text()).toContain('Live updates paused')
    expect(banner.element.parentElement).toBe(main.element)
    expect(banner.element.nextElementSibling).toBe(main.get('.page-back').element)
    await banner.get('button').trigger('click')
    expect(connection.reconnectNow).toHaveBeenCalledOnce()
    await main.get('.page-back').trigger('click')
    expect(back).toHaveBeenCalledOnce()
    status.value = 'reconnecting'
    await nextTick()
    expect(main.get('[role="status"]').text()).toContain('Attempt 2 of 5')
    online.value = false
    await nextTick()
    expect(main.get('[role="status"]').text()).toContain('You are offline')
    expect(main.find('.connectivity-banner__action').exists()).toBe(false)
    online.value = true
    status.value = 'connected'
    await nextTick()
    expect(main.find('[role="status"]').exists()).toBe(false)
  })

  it('keeps the same in-flow reconnect status throughout retry handshakes until connected', async () => {
    attempt.value = 0
    status.value = 'connecting'
    const wrapper = mount(AppShell, {
      props: { showShell: true },
      slots: { default: () => h('button', { class: 'page-back' }, 'Back') },
      global: { plugins: [createPinia()], stubs: {
        SidebarNav: true, BottomNav: true, BackgroundQueueMonitor: true, ThemeToggle: true, NotificationFeed: true
      } }
    })
    mounted.push(wrapper)
    const main = wrapper.get('.main-content')
    expect(main.find('[role="status"]').exists()).toBe(false)
    attempt.value = 2
    status.value = 'reconnecting'
    await nextTick()
    const banner = main.get('[role="status"]')
    const originalText = banner.text()
    expect(originalText).toContain('Reconnecting live updates')
    expect(originalText).toContain('Attempt 2 of 5')
    for (const phase of ['connecting', 'reconnecting', 'connecting']) {
      status.value = phase
      await nextTick()
      const current = main.get('[role="status"]')
      expect(current.element).toBe(banner.element)
      expect(current.text()).toBe(originalText)
      expect(current.classes()).toContain('connectivity-banner--warning')
      expect(current.get('use').attributes('href')).toBe('#icon-refresh-cw')
      expect(current.element.parentElement).toBe(main.element)
      expect(current.element.nextElementSibling).toBe(main.get('.page-back').element)
      expect(current.find('button').exists()).toBe(false)
    }
    attempt.value = 3
    await nextTick()
    expect(banner.text()).toContain('Attempt 3 of 5')
    online.value = false
    await nextTick()
    expect(banner.text()).toContain('You are offline')
    expect(banner.classes()).toContain('connectivity-banner--danger')
    expect(banner.find('button').exists()).toBe(false)
    online.value = true
    for (const phase of ['failed', 'error', 'auth_failed']) {
      status.value = phase
      await nextTick()
      expect(banner.text()).toContain(phase === 'auth_failed' ? 'Session needs attention' : 'Live updates paused')
      expect(banner.find('button').exists()).toBe(phase !== 'auth_failed')
    }
    status.value = 'connecting'
    await nextTick()
    await wrapper.setProps({ showShell: false })
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    await wrapper.setProps({ showShell: true })
    expect(wrapper.get('[role="status"]').text()).toContain('Reconnecting live updates')
    status.value = 'connected'
    await nextTick()
    expect(wrapper.find('.main-content [role="status"]').exists()).toBe(false)
  })

  it('reserves actual natural banner height instead of overlaying interactive content', () => {
    const css = shellSource.match(/\.connectivity-banner \{([\s\S]*?)\n\}/)?.[1]
    expect(css).toBeDefined()
    expect(css).not.toMatch(/position:\s*(fixed|absolute)/)
    expect(css).not.toContain('pointer-events: none')
    expect(shellSource).toMatch(/\.connectivity-banner__action \{[\s\S]*?min-height: 44px/)
  })
})
