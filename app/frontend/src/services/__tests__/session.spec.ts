import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OnboardingWizardView from '@/views/OnboardingWizardView.vue'
import { getSafeReturnPath, loginLocationFor } from '@/services/session'

function jsonResponse(body: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.resetModules()
  window.history.replaceState({}, '', '/')
})

describe('session return destinations', () => {
  it.each([
    ['/streamers/7?tab=history#recording', '/streamers/7?tab=history#recording'],
    ['/videos/42', '/videos/42'],
    ['/', '/'],
  ])('preserves an internal deep link: %s', (candidate, expected) => {
    expect(getSafeReturnPath(candidate)).toBe(expected)
  })

  it.each([undefined, '', 'https://example.invalid', '//example.invalid', 'javascript:alert(1)', '/auth/login'])(
    'rejects an unsafe or recursive return destination: %s',
    (candidate) => {
      expect(getSafeReturnPath(candidate)).toBe('/')
    },
  )

  it('uses a query-only login return target for an allowed deep link', () => {
    expect(loginLocationFor('/live/example')).toEqual({
      path: '/auth/login',
      query: { returnTo: '/live/example' },
    })
  })
})

describe('server-authoritative onboarding session path', () => {
  it('continues incomplete welcome from overview through the real router guard', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/auth/setup') return Promise.resolve(jsonResponse({ setup_required: false, welcome_completed: false }))
      if (url === '/auth/check') return Promise.resolve(jsonResponse({ authenticated: true }))
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { default: router } = await import('@/router')
    await router.push('/')
    await router.isReady()

    expect(router.currentRoute.value.fullPath).toBe('/welcome')
    expect(fetchMock).toHaveBeenCalledWith('/auth/setup', expect.objectContaining({ credentials: 'include' }))
  })

  it('keeps a failed onboarding completion on the wizard so it can be retried', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/auth/setup') return Promise.resolve(jsonResponse({ setup_required: false, welcome_completed: false }))
      if (url === '/auth/onboarding/complete' && init?.method === 'POST') return Promise.resolve(new Response(null, { status: 500 }))
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<main>overview</main>' } },
        { path: '/welcome', component: OnboardingWizardView },
      ],
    })
    await router.push('/welcome?step=done')
    await router.isReady()

    const wrapper = mount(OnboardingWizardView, {
      global: {
        plugins: [router],
        stubs: {
          GlassCard: { template: '<section><slot /></section>' },
          BaseButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })
    await flushPromises()

    await wrapper.get('button:last-child').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/welcome?step=done')
    expect(wrapper.text()).toContain('Could not save onboarding state.')
    expect(fetchMock).toHaveBeenCalledWith('/auth/onboarding/complete', expect.objectContaining({ method: 'POST' }))
    wrapper.unmount()
  })

  it.each([
    [403, 'Access to setup is forbidden. Contact an administrator or sign in with an authorized account.'],
    [503, 'StreamVault setup is currently unavailable. Check the service and try again.'],
  ])('shows a local setup status instead of the admin form for bootstrap HTTP %i', async (status, message) => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(null, { status }))))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/welcome', component: OnboardingWizardView }],
    })
    await router.push('/welcome')
    await router.isReady()
    const wrapper = mount(OnboardingWizardView, {
      global: {
        plugins: [router],
        stubs: {
          GlassCard: { template: '<section><slot /></section>' },
          BaseButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain(message)
    expect(wrapper.text()).not.toContain('Create your administrator credentials')
    wrapper.unmount()
  })

  it('shows an offline setup status instead of guessing that admin setup is required', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('offline'))))

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/welcome', component: OnboardingWizardView }],
    })
    await router.push('/welcome')
    await router.isReady()
    const wrapper = mount(OnboardingWizardView, {
      global: {
        plugins: [router],
        stubs: {
          GlassCard: { template: '<section><slot /></section>' },
          BaseButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        },
      },
    })
    await flushPromises()

    expect(wrapper.get('[role="alert"]').text()).toContain('Could not reach StreamVault setup. Check your connection and try again.')
    expect(wrapper.text()).not.toContain('Create your administrator credentials')
    wrapper.unmount()
  })

  it('sends an expired welcome session and an expired protected deep link to login with safe returns', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/auth/setup') return Promise.resolve(jsonResponse({ setup_required: false, welcome_completed: false }))
      if (url === '/auth/check') return Promise.resolve(new Response(null, { status: 401 }))
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { default: router } = await import('@/router')
    await router.push('/welcome?step=recording')
    await router.isReady()
    expect(router.currentRoute.value.fullPath).toBe('/auth/login?returnTo=/welcome?step=recording')

    await router.push('/videos/42?from=library#details')
    expect(router.currentRoute.value.path).toBe('/auth/login')
    expect(router.currentRoute.value.query.returnTo).toBe('/videos/42?from=library#details')
    expect(fetchMock).toHaveBeenCalledWith('/auth/check', expect.objectContaining({ credentials: 'include' }))
  })

  it('does not misclassify forbidden or offline welcome checks as a terminated session', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/auth/setup') return Promise.resolve(jsonResponse({ setup_required: false, welcome_completed: false }))
      if (url === '/auth/check') return Promise.resolve(new Response(null, { status: 403 }))
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })
    vi.stubGlobal('fetch', fetchMock)

    const { default: router } = await import('@/router')
    await router.push('/welcome')
    await router.isReady()
    expect(router.currentRoute.value.fullPath).toBe('/welcome')

    fetchMock.mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/auth/setup') return Promise.reject(new TypeError('offline'))
      return Promise.reject(new Error(`Unexpected request: ${url}`))
    })
    await router.push('/videos/42')
    expect(router.currentRoute.value.fullPath).toBe('/videos/42')
  })
})
