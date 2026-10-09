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
    expect(source).toContain('Back to System')
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
  })
})
