import { defineComponent, nextTick, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NavigationWrapper from '../NavigationWrapper.vue'
import BaseModal from '@/components/base/BaseModal.vue'

vi.mock('@/composables/useWebSocket', () => ({
  useWebSocket: () => ({
    connectionStatus: { value: 'connected' },
    isBrowserOnline: { value: true },
    reconnectNow: vi.fn(),
  }),
}))

interface LayoutViewport {
  setWidth: (width: number) => void
  query: () => string
}

function stubLayoutViewport(width: number): LayoutViewport {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  let currentWidth = width
  let requestedQuery = ''

  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => {
      requestedQuery = query
      return {
        get matches() {
          return currentWidth <= 1023.98
        },
        media: query,
        addEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) =>
          listeners.add(listener),
        removeEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) =>
          listeners.delete(listener),
        dispatchEvent: () => true,
      }
    }),
  )

  return {
    setWidth(nextWidth) {
      currentWidth = nextWidth
      for (const listener of listeners) {
        listener({ matches: currentWidth <= 1023.98, media: requestedQuery } as MediaQueryListEvent)
      }
    },
    query: () => requestedQuery,
  }
}

async function mountNavigation(width: number, initialRoute = '/streamers/42') {
  const viewport = stubLayoutViewport(width)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div>Dashboard</div>' } },
      { path: '/streamers/:id', component: { template: '<div>Streamer</div>' } },
      { path: '/videos', component: { template: '<div>Library</div>' } },
      { path: '/subscriptions', component: { template: '<div>Subscriptions</div>' } },
      { path: '/settings', component: { template: '<div>Settings</div>' } },
    ],
  })
  await router.push(initialRoute)
  await router.isReady()

  return {
    router,
    viewport,
    wrapper: mount(NavigationWrapper, {
      attachTo: document.body,
      global: { plugins: [router] },
      slots: { default: '<p>Routed content</p>' },
    }),
  }
}

const ModalNavigationHarness = defineComponent({
  components: { BaseModal, NavigationWrapper },
  setup() {
    const open = ref(true)
    return { open }
  },
  template: `
    <NavigationWrapper><p>Routed content</p></NavigationWrapper>
    <BaseModal v-model="open" title="Navigation settings"><button>Save</button></BaseModal>
  `,
})

describe('NavigationWrapper responsive accessibility', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    document.body.style.cssText = ''
    vi.unstubAllGlobals()
  })

  it('uses desktop navigation at 1024px and mobile navigation at 1023.98px without duplicate controls', async () => {
    const desktop = await mountNavigation(1024)

    expect(desktop.viewport.query()).toBe('(max-width: 1023.98px)')
    expect(desktop.wrapper.findAll('aside[aria-label="Application navigation"]')).toHaveLength(1)
    expect(desktop.wrapper.findAll('nav[aria-label="Primary mobile navigation"]')).toHaveLength(0)

    desktop.viewport.setWidth(1023.98)
    await nextTick()

    expect(desktop.wrapper.findAll('aside[aria-label="Application navigation"]')).toHaveLength(0)
    expect(desktop.wrapper.findAll('nav[aria-label="Primary mobile navigation"]')).toHaveLength(1)
    expect(desktop.wrapper.findAll('.sidebar-nav-item, .sidebar-toggle')).toHaveLength(0)
    desktop.wrapper.unmount()
  })

  it('preserves the active route while the layout query switches navigation presentation', async () => {
    const { router, viewport, wrapper } = await mountNavigation(1024)

    expect(wrapper.get('.sidebar-nav-item.active').attributes('href')).toBe('/streamers')
    viewport.setWidth(390)
    await nextTick()

    expect(router.currentRoute.value.path).toBe('/streamers/42')
    expect(wrapper.get('.nav-tab.active').attributes('aria-current')).toBe('page')
    wrapper.unmount()
  })

  it('keeps the modal lifecycle clean when navigation presentation changes', async () => {
    const viewport = stubLayoutViewport(390)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div>Dashboard</div>' } }],
    })
    await router.push('/')
    await router.isReady()
    const trigger = document.createElement('button')
    vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
    document.body.append(trigger)
    trigger.focus()
    const wrapper = mount(ModalNavigationHarness, {
      attachTo: document.body,
      global: { plugins: [router], stubs: { Transition: false } },
    })

    await nextTick()
    expect(document.body.style.overflow).toBe('hidden')
    expect(wrapper.findAll('nav[aria-label="Primary mobile navigation"]')).toHaveLength(1)

    viewport.setWidth(1024)
    await nextTick()
    await wrapper.setData({ open: false })
    await nextTick()

    expect(wrapper.findAll('nav[aria-label="Primary mobile navigation"]')).toHaveLength(0)
    expect(document.body.style.overflow).toBe('')
    expect(document.activeElement).toBe(trigger)
    wrapper.unmount()
  })
})
