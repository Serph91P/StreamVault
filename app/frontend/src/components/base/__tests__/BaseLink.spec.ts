import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import BaseLink from '../BaseLink.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
    { path: '/library', component: { template: '<div />' } },
  ],
})

describe('BaseLink', () => {
  it('renders a native anchor with an accessible name and ordinary target contract', async () => {
    const wrapper = mount(BaseLink, {
      props: { to: '/library' },
      slots: { default: 'Library' },
      global: { plugins: [router] },
    })

    await router.isReady()
    const link = wrapper.get('a')
    expect(link.attributes('href')).toBe('/library')
    expect(link.text()).toBe('Library')
    expect(link.classes()).toContain('base-link-target--ordinary')
  })

  it('uses the 48px icon target contract without replacing native link behavior', async () => {
    const wrapper = mount(BaseLink, {
      props: { to: '/library', targetSize: 'icon', ariaLabel: 'Open library' },
      slots: { default: '<svg aria-hidden="true" />' },
      global: { plugins: [router] },
    })

    await router.isReady()
    const link = wrapper.get('a')
    expect(link.attributes('aria-label')).toBe('Open library')
    expect(link.classes()).toContain('base-link-target--icon')
    expect(link.attributes('role')).toBeUndefined()
    expect(link.attributes('tabindex')).toBeUndefined()
  })
})
