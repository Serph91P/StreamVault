import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { afterEach, describe, expect, it } from 'vitest'
import VideoCard from '../VideoCard.vue'

const video = {
  id: 7,
  streamer_id: 3,
  title: 'Recorded stream',
  created_at: '2026-01-01T00:00:00Z',
}

async function mountCard(origin = '/videos?q=alpha#recordings') {
  history.replaceState({ preserved: 'state' }, '', origin)
  const router = createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/videos', name: 'videos', component: { template: '<div />' } },
      { path: '/streamer/:streamerId/stream/:streamId/watch', name: 'VideoPlayer', component: { template: '<div />' } },
    ],
  })
  await router.push(origin)
  await router.isReady()

  return {
    router,
    wrapper: mount(VideoCard, {
      attachTo: document.body,
      props: { video, origin },
      global: { plugins: [router] },
    }),
  }
}

async function clickLink(wrapper: ReturnType<typeof mount>, init: MouseEventInit = {}) {
  const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...init })
  wrapper.get('a.video-card-link').element.dispatchEvent(event)
  await new Promise((resolve) => setTimeout(resolve, 0))
}

async function returnToSourceHistoryEntry() {
  const returned = new Promise<void>((resolve) => window.addEventListener('popstate', () => resolve(), { once: true }))
  history.back()
  await returned
}

describe('VideoCard RouterLink return snapshots', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    history.replaceState({}, '', '/')
  })

  it.each([
    ['Ctrl', { ctrlKey: true }],
    ['Meta', { metaKey: true }],
    ['Alt', { altKey: true }],
    ['Shift', { shiftKey: true }],
    ['secondary button', { button: 1 }],
  ])('does not mutate the source tab for a %s RouterLink activation', async (_name, event) => {
    const origin = '/videos?q=alpha#recordings'
    const { router, wrapper } = await mountCard(origin)
    const before = { href: location.href, state: history.state, route: router.currentRoute.value.fullPath }

    await clickLink(wrapper, event)

    expect({
      href: location.href,
      state: history.state,
      route: router.currentRoute.value.fullPath,
    }).toEqual(before)
    wrapper.unmount()
  })

  it('does not mutate the source tab when a parent capture handler already prevented the event', async () => {
    const origin = '/videos?q=alpha#recordings'
    const { router, wrapper } = await mountCard(origin)
    const before = { href: location.href, state: history.state, route: router.currentRoute.value.fullPath }
    const prevent = (event: Event) => event.preventDefault()
    document.body.addEventListener('click', prevent, { capture: true })

    await clickLink(wrapper)

    document.body.removeEventListener('click', prevent, { capture: true })
    expect({ href: location.href, state: history.state, route: router.currentRoute.value.fullPath }).toEqual(before)
    wrapper.unmount()
  })

  it('does not mutate the source tab when the link targets another browsing context', async () => {
    const origin = '/videos?q=alpha#recordings'
    const { router, wrapper } = await mountCard(origin)
    const link = wrapper.get('a.video-card-link')
    link.element.setAttribute('target', '_blank')
    const before = { href: location.href, state: history.state, route: router.currentRoute.value.fullPath }

    await clickLink(wrapper)

    expect({ href: location.href, state: history.state, route: router.currentRoute.value.fullPath }).toEqual(before)
    wrapper.unmount()
  })

  it('keeps the return snapshot for an ordinary primary RouterLink click', async () => {
    const origin = '/videos?q=alpha#recordings'
    const { router, wrapper } = await mountCard(origin)

    await clickLink(wrapper)

    expect(router.currentRoute.value.fullPath).toBe('/streamer/3/stream/7/watch')
    expect(location.pathname + location.search + location.hash).toBe('/streamer/3/stream/7/watch')
    await returnToSourceHistoryEntry()
    expect(location.pathname + location.search + location.hash).toBe(origin)
    expect(history.state.svre).toEqual({ origin, expanded: {} })
    expect(history.state.svrs).toBeTypeOf('number')
    wrapper.unmount()
  })

  it('keeps a zero-detail primary click eligible for a return snapshot', async () => {
    const origin = '/videos?q=alpha#recordings'
    const { router, wrapper } = await mountCard(origin)

    await clickLink(wrapper, { detail: 0 })

    expect(router.currentRoute.value.fullPath).toBe('/streamer/3/stream/7/watch')
    await returnToSourceHistoryEntry()
    expect(history.state.svre).toEqual({ origin, expanded: {} })
    wrapper.unmount()
  })
})
