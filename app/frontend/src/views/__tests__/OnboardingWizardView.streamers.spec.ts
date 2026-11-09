import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OnboardingWizardView from '../OnboardingWizardView.vue'

const wrappers: ReturnType<typeof mount>[] = []
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

async function wizard(add: (request: Request) => Promise<Response>) {
  const requests: Request[] = []
  vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
    const request = new Request(new URL(url, 'http://localhost'), init)
    requests.push(request)
    if (url === '/auth/setup') return Response.json({ setup_required: false, welcome_completed: false })
    if (url === '/api/recording/settings') return Response.json({ default_quality: '480p', enabled: false })
    if (url.startsWith('/api/streamers/')) return add(request)
    throw new Error(`Unexpected request: ${url}`)
  })
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/welcome', component: OnboardingWizardView },
  ] })
  await router.push('/welcome?step=streamers')
  const wrapper = mount(OnboardingWizardView, { global: { plugins: [router], directives: { ripple: {} } } })
  wrappers.push(wrapper)
  await flushPromises()
  return { wrapper, router, requests }
}

describe('onboarding first channel', () => {
  it('sends only the required empty JSON object with the session and normalized name', async () => {
    const { wrapper, requests, router } = await wizard(async () => Response.json({ id: 995, username: 'synthetic995' }))
    await wrapper.get('input[placeholder="Twitch username"]').setValue('  @synthetic995  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    const request = requests.find(r => r.method === 'POST')!
    expect(request.headers.get('Content-Type')).toBe('application/json')
    expect(await request.json()).toEqual({})
    expect(request.credentials).toBe('include')
    expect(new URL(request.url).pathname).toBe('/api/streamers/synthetic995')
    expect(wrapper.get('.added-streamers').text()).toBe('synthetic995')
    expect(wrapper.get<HTMLInputElement>('input').element.value).toBe('')
    expect(router.currentRoute.value.query.step).toBe('streamers')
    expect(requests.filter(r => r.method === 'POST')).toHaveLength(1)
  })

  it.each([
    [422, { detail: [{ loc: ['body'], msg: 'Field required', type: 'missing' }] }],
    [400, { detail: 'Failed to add streamer' }],
    [500, { detail: 'Internal server error' }],
    [503, null],
  ])('keeps the draft and step without success after HTTP %s', async (status, body) => {
    const { wrapper, requests, router } = await wizard(async () => Response.json(body, { status }))
    await wrapper.get('input').setValue('@synthetic995')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('input').element.value).toBe('@synthetic995')
    expect(wrapper.get('.error-banner').text()).not.toBe('')
    expect(wrapper.find('.added-streamers').exists()).toBe(false)
    expect(router.currentRoute.value.query.step).toBe('streamers')
    expect(requests.some(r => r.url.includes('/onboarding/complete'))).toBe(false)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })

  it('blocks overlapping submits until the response, then permits retry after a network failure', async () => {
    let reject!: (reason: Error) => void
    let calls = 0
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { wrapper } = await wizard(async () => {
      calls++
      if (calls === 1) return new Promise<Response>((_, fail) => { reject = fail })
      return Response.json({ id: 995, username: 'synthetic995' })
    })
    await wrapper.get('input').setValue('synthetic995')
    await wrapper.get('form').trigger('submit')
    await wrapper.get('form').trigger('submit')
    expect(calls).toBe(1)
    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.added-streamers').exists()).toBe(false)
    reject(new TypeError('Network unavailable'))
    await flushPromises()
    expect(wrapper.get('.error-banner').text()).toContain('Connection failed')
    expect(wrapper.get<HTMLInputElement>('input').element.value).toBe('synthetic995')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(calls).toBe(2)
    expect(wrapper.find('.error-banner').exists()).toBe(false)
    expect(wrapper.findAll('.added-streamers li')).toHaveLength(1)
  })

  it('ignores empty names and keeps manual navigation available with the draft intact', async () => {
    const { wrapper, requests } = await wizard(async () => { throw new Error('Must not add') })
    for (const name of [' ', '@']) {
      await wrapper.get('input').setValue(name)
      await wrapper.get('form').trigger('submit')
    }
    expect(requests.filter(r => r.method === 'POST')).toHaveLength(0)
    await wrapper.get('input').setValue('draft995')
    await wrapper.findAll('button').find(b => b.text() === 'Back')!.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find(b => b.text() === 'Save & Continue')!.trigger('click')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('input').element.value).toBe('draft995')
    expect(wrapper.findAll('button').some(b => b.text() === 'Skip & Continue' && b.attributes('disabled') === undefined)).toBe(true)
  })
})
