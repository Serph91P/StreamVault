import { describe, expect, it } from 'vitest'
import router from '../index'

const componentAt = (path: string) => router.resolve(path).matched.at(-1)?.components?.default

describe('channel-first route preservation', () => {
  it('opens the existing channels application at the root without losing the overview', () => {
    expect(componentAt('/')).toBe(componentAt('/streamers'))
    expect(router.resolve('/overview').name).toBe('overview')
    expect(componentAt('/overview')).not.toBe(componentAt('/'))
  })

  it('does not overwrite entry restoration or in-page filter scroll', async () => {
    const normalized = (path: string) => ({ ...router.resolve(path), name: router.resolve(path).name ?? undefined })
    const list = normalized('/streamers?q=demo')
    const detail = normalized('/streamers/42')
    history.replaceState({ svrs: 420 }, '', '/streamers?q=demo')
    expect(await router.options.scrollBehavior!(list, detail, null)).toBe(false)
    history.replaceState({}, '', '/streamers?q=demo')
    expect(await router.options.scrollBehavior!(list, normalized('/streamers'), null)).toBe(false)
    expect(await router.options.scrollBehavior!(list, detail, { left: 0, top: 420 })).toBe(false)
    expect(history.state.svrs).toBe(420)
    delete history.state.svrs
    history.replaceState({}, '', '/streamers?q=demo')
    expect(await router.options.scrollBehavior!(detail, list, null)).toEqual({ top: 0, left: 0 })
  })

  it('resolves channel management separately from a channel detail', () => {
    expect(router.resolve('/streamers/manage').name).toBe('channel-management')
    expect(componentAt('/streamers/manage')).not.toBe(componentAt('/streamers/7'))
  })

  it('keeps every existing route name and exposes activity separately', () => {
    const names = router.getRoutes().map(route => route.name)
    expect(names).toEqual(expect.arrayContaining([
      'home', 'welcome', 'streamers', 'videos', 'video-player', 'subscriptions',
      'add-streamer', 'add-streamer-manual', 'add-streamer-import', 'setup',
      'onboarding', 'login', 'system', 'Admin', 'settings', 'streamer-detail',
      'VideoPlayer', 'live-player', 'activity', 'overview',
    ]))
  })
})
