import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import SystemHubView from '../SystemHubView.vue'
import systemHubSource from '../SystemHubView.vue?raw'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/system', component: SystemHubView },
    { path: '/settings', component: { template: '<main>Settings</main>' } },
    { path: '/admin', component: { template: '<main>Admin</main>' } },
    { path: '/subscriptions', component: { template: '<main>Subscriptions</main>' } },
  ],
})

describe('SystemHubView', () => {
  it('keeps the three existing destinations as complete, labelled card links', async () => {
    await router.push('/system')
    await router.isReady()

    const wrapper = mount(SystemHubView, { global: { plugins: [router] } })
    const links = wrapper.findAll('.system-hub-card')

    expect(links.map(link => link.attributes('href'))).toEqual(['/settings', '/admin', '/subscriptions'])
    expect(links.map(link => link.attributes('aria-label'))).toEqual(['Settings', 'Admin tools', 'Subscriptions'])
    expect(links.every(link => link.find('svg').exists())).toBe(true)
    expect(links.every(link => link.find('strong').exists() && link.find('small').exists())).toBe(true)
  })

  it('defines an opaque responsive grid with controlled icons and keyboard-visible links', () => {
    expect(systemHubSource).toMatch(/\.system-hub-grid\s*\{[\s\S]*?display:\s*grid;/)
    expect(systemHubSource).toMatch(/\.system-hub-card\s*\{[\s\S]*?min-height:\s*44px;/)
    expect(systemHubSource).toMatch(/\.system-hub-card\s*\{[\s\S]*?background:\s*var\(--sv-cmp-panel-background\);/)
    expect(systemHubSource).toMatch(/\.system-hub-card\s*\{[\s\S]*?backdrop-filter:\s*none;/)
    expect(systemHubSource).toMatch(/\.system-hub-icon svg\s*\{[\s\S]*?width:\s*24px;[\s\S]*?height:\s*24px;/)
    expect(systemHubSource).toMatch(/\.system-hub-card:focus-visible\s*\{/)
    expect(systemHubSource).toMatch(/respond-below\('sm'\)[\s\S]*?grid-template-columns:\s*1fr;/)
  })
})
