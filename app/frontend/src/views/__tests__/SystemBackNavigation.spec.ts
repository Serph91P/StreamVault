import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import PageHeader from '@/components/base/PageHeader.vue'
import AdminViewSource from '../AdminView.vue?raw'
import SettingsViewSource from '../SettingsView.vue?raw'
import SubscriptionsViewSource from '../SubscriptionsView.vue?raw'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/system', component: { template: '<main>System</main>' } },
  ],
})

describe('system back navigation', () => {
  it.each([
    ['Settings', SettingsViewSource],
    ['Admin tools', AdminViewSource],
    ['Subscriptions', SubscriptionsViewSource],
  ])('provides a stable Back to System link on %s', (_name, source) => {
    expect(source).toContain(_name === 'Settings' ? 'Zurück zum System' : 'Back to System')
    expect(source).toContain('/system')
  })

  it('renders the shared back action as an accessible router link', async () => {
    await router.push('/system')
    await router.isReady()

    const wrapper = mount(PageHeader, {
      props: { title: 'Settings', backTo: '/system', backLabel: 'Back to System' },
      global: { plugins: [router] },
    })

    const link = wrapper.get('a[href="/system"]')
    expect(link.text()).toContain('Back to System')
    expect(link.attributes('aria-label')).toBe('Back to System')
    expect(link.classes()).toContain('page-header-back-link')
    wrapper.unmount()
  })

  it('separates nested navigation from both responsive title identities', () => {
    const wrapper = mount(PageHeader, {
      props: { title: 'Settings', icon: 'settings', mobileTitle: 'Twitch Connection', mobileIcon: 'twitch', backTo: '/system' },
      global: { plugins: [router] },
    })
    try {
      expect(wrapper.find('.page-header-back-row a[href="/system"]').exists()).toBe(true)
      expect(wrapper.get('.desktop-title svg use').attributes('href')).toBe('#icon-settings')
      expect(wrapper.get('.mobile-title svg use').attributes('href')).toBe('#icon-twitch')
      expect(wrapper.get('.desktop-title').text()).toBe('Settings')
      expect(wrapper.get('.mobile-title').text()).toBe('Twitch Connection')
    } finally {
      wrapper.unmount()
    }
  })

  it('preserves ordinary headers without a back action', () => {
    const wrapper = mount(PageHeader, { props: { title: 'Streamers', icon: 'users', subtitle: 'Existing description' } })
    try {
      expect(wrapper.find('.page-header-back-row').exists()).toBe(false)
      expect(wrapper.find('.page-header-title-group > svg').exists()).toBe(true)
      expect(wrapper.find('.desktop-title svg').exists()).toBe(false)
      expect(wrapper.get('h1').text()).toBe('Streamers')
      expect(wrapper.get('.page-header-subtitle').text()).toBe('Existing description')
    } finally {
      wrapper.unmount()
    }
  })
})
