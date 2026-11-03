import { describe, expect, it } from 'vitest'
import router from '../index'

const componentAt = (path: string) => router.resolve(path).matched.at(-1)?.components?.default

describe('channel-first route preservation', () => {
  it('opens the existing channels application at the root without losing the overview', () => {
    expect(componentAt('/')).toBe(componentAt('/streamers'))
    expect(router.resolve('/overview').name).toBe('overview')
    expect(componentAt('/overview')).not.toBe(componentAt('/'))
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
