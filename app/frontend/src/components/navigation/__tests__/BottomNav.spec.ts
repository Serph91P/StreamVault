import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import BottomNav from '../BottomNav.vue'

const { connectionStatus, isBrowserOnline } = vi.hoisted(() => ({
  connectionStatus: { value: 'connected' },
  isBrowserOnline: { value: true },
}))

vi.mock('@/composables/useNavigation', () => ({
  useNavigation: () => ({
    navigationTabs: [{ route: '/library', label: 'Library', icon: 'library' }],
    isMobile: { value: true },
    isActiveRoute: (route: string) => route === '/library',
  }),
}))

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    connectionStatus,
    isBrowserOnline,
    reconnectNow: vi.fn(),
  }),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
    { path: '/library', component: { template: '<div />' } },
  ],
})

describe('BottomNav', () => {
  it('uses a native router link for a navigation route instead of click-simulated navigation', async () => {
    const wrapper = mount(BottomNav, { global: { plugins: [router] } })

    await router.isReady()
    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe('/library')
    expect(link.attributes('aria-label')).toBe('Library')
    expect(link.attributes('aria-current')).toBe('page')
    expect(link.classes()).toContain('base-link-target--icon')
    expect(wrapper.find('button.nav-tab').exists()).toBe(false)
  })

  it('renders Retry only for an online failed pill', async () => {
    connectionStatus.value = 'failed'
    isBrowserOnline.value = true
    const wrapper = mount(BottomNav, { global: { plugins: [router] } })

    await router.isReady()

    expect(wrapper.get('.mobile-connectivity-pill__action').text()).toBe('Retry')

    wrapper.unmount()
    connectionStatus.value = 'connected'
  })
})
