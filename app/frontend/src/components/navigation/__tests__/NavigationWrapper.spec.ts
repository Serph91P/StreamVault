import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NavigationWrapper from '../NavigationWrapper.vue'
import navigationWrapperSource from '../NavigationWrapper.vue?raw'

const { useSwipeMock } = vi.hoisted(() => ({
  useSwipeMock: vi.fn(() => ({ lengthX: { value: 0 } })),
}))

vi.mock('@vueuse/core', () => ({
  useSwipe: useSwipeMock,
}))

vi.mock('@/composables/useNavigation', () => ({
  useNavigation: () => ({
    isMobile: { value: true },
    isDesktop: { value: false },
    sidebarExpanded: { value: false },
    navigateNext: vi.fn(),
    navigatePrevious: vi.fn(),
  }),
}))

describe('NavigationWrapper touch navigation', () => {
  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('does not depend on the global swipe-navigation composable', () => {
    expect(navigationWrapperSource).not.toMatch(/useSwipeNavigation/)
  })

  it('does not register global route-swipe listeners', async () => {
    vi.useFakeTimers()
    const wrapper = mount(NavigationWrapper, {
      global: {
        stubs: {
          BottomNav: true,
          SidebarNav: true,
        },
      },
    })

    await vi.runAllTimersAsync()
    wrapper.unmount()

    expect(useSwipeMock).not.toHaveBeenCalled()
  })
})
