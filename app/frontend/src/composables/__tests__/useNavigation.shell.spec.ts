import { describe, expect, it } from 'vitest'
import { navigationTabs } from '@/composables/useNavigation'

describe('shell navigation contract', () => {
  it('exposes the four task-oriented destinations with System as the technical-page hub', () => {
    expect(navigationTabs.map((tab) => [tab.route, tab.label])).toEqual([
      ['/', 'Overview'],
      ['/streamers', 'Streamers'],
      ['/videos', 'Library'],
      ['/system', 'System'],
    ])
  })
})
