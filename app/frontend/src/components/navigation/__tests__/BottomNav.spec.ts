import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import BottomNav from '../BottomNav.vue'

vi.mock('@/composables/useNavigation', () => ({
  useNavigation: () => ({
    navigationTabs: [{ route: '/library', label: 'Library', icon: 'library' }],
    isMobile: { value: true },
    isActiveRoute: (route: string) => route === '/library',
  }),
}))

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    connectionStatus: { value: 'connected' },
    isBrowserOnline: { value: true },
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
})
