import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import StreamerCard from '../StreamerCard.vue'
import streamerCardSource from '../StreamerCard.vue?raw'

const streamer = {
  id: 42,
  username: 'streamer-alpha',
  display_name: 'Streamer Alpha',
  description: 'A test streamer',
}

async function mountCard() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/streamers/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  await router.isReady()

  return {
    router,
    wrapper: mount(StreamerCard, {
      attachTo: document.body,
      props: { streamer },
      global: { plugins: [router] },
    }),
  }
}

function detailLinks(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('a').filter((link) => link.attributes('href') === `/streamers/${streamer.id}`)
}

describe('StreamerCard touch and navigation behavior', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('does not own long-press state or suppression behavior', () => {
    const forbiddenContracts = [
      ['long-press timer', /LONG_PRESS_MS|longPressTimer/],
      ['touch-coordinate state', /touchStart[XY]|longPressPoint/],
      ['capture click suppression', /armClickSuppression|suppressNextClick/],
      ['context-menu suppression', /@contextmenu|handleContextMenu/],
      ['long-press vibration', /navigator\.vibrate/],
    ]
      .filter(([, pattern]) => (pattern as RegExp).test(streamerCardSource))
      .map(([name]) => name)

    expect(forbiddenContracts).toEqual([])
  })

  it('does not open actions or vibrate when the card is held', async () => {
    vi.useFakeTimers()
    const vibrate = vi.fn()
    vi.stubGlobal('navigator', { vibrate })
    const { wrapper } = await mountCard()

    await wrapper.get('.streamer-card-content').trigger('touchstart', {
      touches: [{ clientX: 40, clientY: 60 }],
    })
    await vi.advanceTimersByTimeAsync(500)

    const behavior = {
      actionsOpened: document.body.querySelector('.actions-dropdown') !== null,
      vibrated: vibrate.mock.calls.length > 0,
    }
    wrapper.unmount()

    expect(behavior).toEqual({ actionsOpened: false, vibrated: false })
  })

  it('renders no empty card overlay and one visible View details link', async () => {
    const { wrapper } = await mountCard()
    const links = detailLinks(wrapper)
    const linkContract = {
      emptyDetailLinks: links.filter((link) => link.text().trim() === '').length,
      visibleViewDetailsLinks: links.filter(
        (link) => link.text().trim() === 'View details' && link.attributes('aria-label') === 'View details',
      ).length,
    }
    wrapper.unmount()

    expect(linkContract).toEqual({ emptyDetailLinks: 0, visibleViewDetailsLinks: 1 })
  })

  it('navigates once only from the visible View details control', async () => {
    const { router, wrapper } = await mountCard()
    const push = vi.spyOn(router, 'push')

    await wrapper.get('.stream-info-container').trigger('click')
    expect(push).not.toHaveBeenCalled()

    const visibleLinks = detailLinks(wrapper).filter((link) => link.text().trim() === 'View details')
    expect(visibleLinks).toHaveLength(1)
    await visibleLinks[0].trigger('click')
    expect(push).toHaveBeenCalledTimes(1)
    expect(push).toHaveBeenCalledWith(`/streamers/${streamer.id}`)

    wrapper.unmount()
  })

  it('opens only from the 48px overflow button and exposes one menu relationship', async () => {
    const { wrapper } = await mountCard()
    const button = wrapper.get('button.btn-more')
    const menuId = button.attributes('aria-controls')

    expect({
      hasPopup: button.attributes('aria-haspopup'),
      expanded: button.attributes('aria-expanded'),
      hasStableControl: Boolean(menuId),
      exactSize: /\.btn-action\s*\{[\s\S]*?width:\s*48px;[\s\S]*?height:\s*48px;/.test(streamerCardSource),
    }).toEqual({ hasPopup: 'menu', expanded: 'false', hasStableControl: true, exactSize: true })

    await button.trigger('click')
    const menu = document.body.querySelector<HTMLElement>('[role="menu"]')
    expect({
      expanded: button.attributes('aria-expanded'),
      menuId: menu?.id,
      duplicateDetailsAction: menu?.textContent?.includes('View Details'),
    }).toEqual({ expanded: 'true', menuId, duplicateDetailsAction: false })

    ;(button.element as HTMLButtonElement).focus()
    await button.trigger('keydown', { key: 'Escape' })
    expect(button.attributes('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(button.element)
    expect(document.body.querySelector('[role="menu"]')).toBeNull()

    wrapper.unmount()
  })

  it('keeps card surfaces vertical-pan friendly without making the card clickable', () => {
    expect(streamerCardSource).toMatch(/\.streamer-card\s*\{[\s\S]*?touch-action:\s*pan-y;/)
    expect(streamerCardSource).not.toMatch(/\.streamer-card-content\s*\{[^}]*cursor:\s*pointer;/)
  })
})
